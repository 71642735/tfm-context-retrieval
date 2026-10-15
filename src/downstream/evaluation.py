import subprocess
from dataclasses import dataclass
from pathlib import Path

import docker
import swebench.harness.run_evaluation as swe_run

from src.contextbench import load_task
from src.repo_manager import prepare_repository


MODEL = "gemini-3.5-flash-lite"
EVALUATION_TIMEOUT = 1800
TEST_EXIT_MARKER = ">>>>> Test Exit Code:"


@dataclass
class EvaluationResult:
    task_id: str
    retrieval_method: str
    status: str
    resolved: bool | None
    patch_path: Path
    infrastructure_failure: bool
    detail: str | None = None


def podman_compatible_cleanup(
    client,
    container,
    logger,
) -> None:
    """
    Adaptación de compatibilidad para Podman.

    SWE-bench 5.0.2 utiliza el CLI de Docker durante el cleanup.
    En este entorno se realiza el cleanup mediante Docker SDK,
    conectado a la API compatible de Podman.
    """
    if not container:
        return

    try:
        logger.info(
            f"Stopping container {container.name} "
            "through Docker SDK / Podman..."
        )
        container.stop(timeout=15)

    except Exception as exc:
        logger.warning(
            f"Could not stop container normally: {exc}"
        )

        try:
            container.kill()
        except Exception as kill_exc:
            logger.warning(
                f"Could not kill container: {kill_exc}"
            )

    try:
        logger.info(
            f"Removing container {container.name} "
            "through Docker SDK / Podman..."
        )
        container.remove(force=True)

    except Exception as exc:
        logger.warning(
            f"Could not remove container: {exc}"
        )


def run_with_windows_podman_compatibility(
    test_spec,
    pred,
    client,
    run_id,
    timeout,
):
    """
    Ejecuta SWE-bench aplicando únicamente adaptaciones
    de infraestructura para Windows + Podman.

    La lógica de tests y grading de SWE-bench no se modifica.
    """
    original_write_text = Path.write_text
    original_cleanup = swe_run.cleanup_container

    def write_text_lf(
        self,
        data,
        encoding=None,
        errors=None,
        newline=None,
    ):
        return original_write_text(
            self,
            data,
            encoding=encoding,
            errors=errors,
            newline="\n",
        )

    try:
        Path.write_text = write_text_lf
        swe_run.cleanup_container = podman_compatible_cleanup

        return swe_run.run_instance(
            test_spec=test_spec,
            pred=pred,
            client=client,
            run_id=run_id,
            timeout=timeout,
            rewrite_reports=False,
        )

    finally:
        Path.write_text = original_write_text
        swe_run.cleanup_container = original_cleanup


def check_patch_applies(
    repo_root: Path,
    patch_path: Path,
) -> tuple[bool, str | None]:
    """
    Comprueba si Git puede aplicar el patch sin modificar
    el repositorio.
    """
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "apply",
            "--check",
            str(patch_path.resolve()),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode == 0:
        return True, None

    detail = (
        result.stderr.strip()
        or result.stdout.strip()
        or "git apply --check failed"
    )

    return False, detail


def has_complete_test_output(
    run_id: str,
    task_id: str,
) -> bool:
    """
    Comprueba si SWE-bench llegó a escribir una salida de tests
    completa antes de un posible fallo posterior de infraestructura.
    """
    model_dir = MODEL.replace("/", "__")

    test_output_path = (
        Path("logs")
        / "run_evaluation"
        / run_id
        / model_dir
        / task_id
        / "test_output.txt"
    )

    if not test_output_path.exists():
        return False

    try:
        test_output = test_output_path.read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeError):
        return False

    return TEST_EXIT_MARKER in test_output


def recover_report_from_test_output(
    test_spec,
    pred,
    client,
    run_id: str,
):
    """
    Ejecuta únicamente el grader oficial de SWE-bench sobre
    una salida de tests previamente validada como completa.
    """
    return swe_run.run_instance(
        test_spec=test_spec,
        pred=pred,
        client=client,
        run_id=run_id,
        timeout=EVALUATION_TIMEOUT,
        rewrite_reports=True,
    )


def ensure_podman_image(image: str) -> None:
    """
    Garantiza que la imagen SWE-bench esté disponible localmente.

    Se utiliza Podman CLI para evitar depender de la descarga de
    imágenes mediante Docker SDK, que ha resultado inestable en
    Windows con el backend de Podman.
    """
    inspect_result = subprocess.run(
        [
            "podman",
            "image",
            "exists",
            image,
        ],
        capture_output=True,
        text=True,
    )

    if inspect_result.returncode == 0:
        print("Imagen SWE-bench disponible localmente.")
        return

    print("Imagen SWE-bench no disponible.")
    print("Descargando imagen mediante Podman...")

    pull_result = subprocess.run(
        [
            "podman",
            "pull",
            image,
        ],
        text=True,
    )

    if pull_result.returncode != 0:
        raise RuntimeError(
            "No se pudo descargar la imagen SWE-bench "
            f"mediante Podman: {image}"
        )

    print("Imagen SWE-bench descargada correctamente.")


def evaluate_patch(
    task_id: str,
    patch_path: Path,
    retrieval_method: str,
) -> EvaluationResult:
    """
    Evalúa un único patch mediante SWE-bench.

    Estados posibles:
    - resolved
    - not_resolved
    - invalid_patch
    - infrastructure_error
    """
    task = load_task(task_id)

    repo_root = prepare_repository(
        repository=task["repo"],
        repo_url=task["repo_url"],
        base_commit=task["base_commit"],
    )

    print()
    print("=== VALIDACIÓN DEL PATCH ===")
    print(f"Tarea:  {task_id}")
    print(f"Método: {retrieval_method}")
    print(f"Patch:  {patch_path}")

    patch_applies, patch_error = check_patch_applies(
        repo_root=repo_root,
        patch_path=patch_path,
    )

    if not patch_applies:
        print("Estado: invalid_patch")

        return EvaluationResult(
            task_id=task_id,
            retrieval_method=retrieval_method,
            status="invalid_patch",
            resolved=False,
            patch_path=patch_path,
            infrastructure_failure=False,
            detail=patch_error,
        )

    print("Patch aplicable: sí")
    print()
    print("Cargando instancia oficial de SWE-bench...")

    try:
        instances = swe_run.load_swebench_dataset(
            instance_ids=[task_id]
        )

        if len(instances) != 1:
            raise RuntimeError(
                f"Se esperaba una instancia SWE-bench "
                f"para {task_id}, pero se obtuvieron "
                f"{len(instances)}."
            )

        instance = instances[0]

        print("Construyendo TestSpec...")
        test_spec = swe_run.make_test_spec(instance)

        print(f"Imagen SWE-bench: {test_spec.image}")
        ensure_podman_image(test_spec.image)

        patch = patch_path.read_text(
            encoding="utf-8"
        )

        pred = {
            "instance_id": task_id,
            "model_name_or_path": MODEL,
            "model_patch": patch,
        }

        run_id = (
            f"downstream-{retrieval_method}"
        )

        print(
            "Conectando con Podman mediante Docker SDK..."
        )
        client = docker.from_env()

        print("Ejecutando evaluación SWE-bench...")

        raw_result = run_with_windows_podman_compatibility(
            test_spec=test_spec,
            pred=pred,
            client=client,
            run_id=run_id,
            timeout=EVALUATION_TIMEOUT,
        )

    except Exception as exc:
        print(
            f"Estado: infrastructure_error ({exc})"
        )

        return EvaluationResult(
            task_id=task_id,
            retrieval_method=retrieval_method,
            status="infrastructure_error",
            resolved=None,
            patch_path=patch_path,
            infrastructure_failure=True,
            detail=str(exc),
        )

    if raw_result is None:
        print(
            "SWE-bench no devolvió report en la "
            "ejecución normal."
        )

        if not has_complete_test_output(
            run_id=run_id,
            task_id=task_id,
        ):
            print(
                "Estado: infrastructure_error "
                "(no existe una salida de tests completa)"
            )

            return EvaluationResult(
                task_id=task_id,
                retrieval_method=retrieval_method,
                status="infrastructure_error",
                resolved=None,
                patch_path=patch_path,
                infrastructure_failure=True,
                detail=(
                    "SWE-bench returned None and no "
                    "complete test output was found."
                ),
            )

        print(
            "Salida de tests completa detectada. "
            "Recuperando grader oficial..."
        )

        try:
            raw_result = recover_report_from_test_output(
                test_spec=test_spec,
                pred=pred,
                client=client,
                run_id=run_id,
            )
        except Exception as exc:
            return EvaluationResult(
                task_id=task_id,
                retrieval_method=retrieval_method,
                status="infrastructure_error",
                resolved=None,
                patch_path=patch_path,
                infrastructure_failure=True,
                detail=(
                    "Could not recover SWE-bench report "
                    f"from complete test output: {exc}"
                ),
            )

        if raw_result is None:
            return EvaluationResult(
                task_id=task_id,
                retrieval_method=retrieval_method,
                status="infrastructure_error",
                resolved=None,
                patch_path=patch_path,
                infrastructure_failure=True,
                detail=(
                    "SWE-bench report recovery returned None."
                ),
            )

    returned_task_id, report = raw_result

    if returned_task_id != task_id:
        return EvaluationResult(
            task_id=task_id,
            retrieval_method=retrieval_method,
            status="infrastructure_error",
            resolved=None,
            patch_path=patch_path,
            infrastructure_failure=True,
            detail=(
                "SWE-bench returned an unexpected "
                f"instance_id: {returned_task_id}"
            ),
        )

    try:
        resolved = bool(
            report[task_id]["resolved"]
        )

    except (KeyError, TypeError) as exc:
        return EvaluationResult(
            task_id=task_id,
            retrieval_method=retrieval_method,
            status="infrastructure_error",
            resolved=None,
            patch_path=patch_path,
            infrastructure_failure=True,
            detail=(
                "Invalid SWE-bench report structure: "
                f"{exc}"
            ),
        )

    status = (
        "resolved"
        if resolved
        else "not_resolved"
    )

    print()
    print("=== RESULTADO SWE-BENCH ===")
    print(f"Estado:   {status}")
    print(f"Resolved: {resolved}")

    return EvaluationResult(
        task_id=task_id,
        retrieval_method=retrieval_method,
        status=status,
        resolved=resolved,
        patch_path=patch_path,
        infrastructure_failure=False,
    )