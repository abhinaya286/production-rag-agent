# Learning Projects

The `simple-local-rag` directory is a Git submodule, not a copied source tree. It
points to the upstream tutorial repository so that its original history and
attribution remain intact.

Initialize or refresh it with:

```powershell
git submodule update --init --recursive
```

Open [`simple-local-rag/README.md`](./simple-local-rag/README.md) for that tutorial's
hardware requirements and notebook setup. The tutorial targets local GPU inference;
the separate [`../production-api/`](../production-api/) project demonstrates a hosted
Gemini and pgvector deployment instead.
