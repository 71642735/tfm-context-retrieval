# Repository Context Retrieval for LLM-Based Software Issue Resolution

## Overview

This repository contains the experimental implementation developed for a Master's Thesis (TFM) investigating how different code retrieval strategies affect the context provided to Large Language Models (LLMs) for software issue resolution.

The study addresses two main research questions:

1. How do lexical, semantic, and hybrid retrieval strategies compare when retrieving relevant code from software repositories?
2. To what extent does retrieval quality relate to an LLM's ability to generate patches that successfully resolve software issues?

The experiments use real software issues from ContextBench and evaluate retrieval quality independently from downstream issue resolution.

## Retrieval Strategies

Three retrieval strategies are compared:

| Strategy         | Description                                                                             |
| ---------------- | --------------------------------------------------------------------------------------- |
| **BM25**         | Lexical retrieval based on term matching between the issue description and code chunks. |
| **UniXcoder**    | Semantic retrieval using vector representations of issue descriptions and code chunks.  |
| **Hybrid (RRF)** | Combines BM25 and UniXcoder rankings using Reciprocal Rank Fusion.                      |

All three strategies operate on the same code chunks to ensure a controlled comparison.

### Code Chunking

Python repositories are divided into code chunks using an AST-based approach, primarily based on functions and methods.

Each chunk retains metadata such as its file path, symbol, source code, and line boundaries.

### Hybrid
