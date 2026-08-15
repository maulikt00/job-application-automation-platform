"""Abstract interfaces (ports) that the application layer depends on.

Infrastructure implementations (SQLite repositories, Claude/Ollama
providers, Playwright engine, website connectors) satisfy these
contracts. Use cases never import infrastructure directly -- they
only ever depend on these interfaces, which is what allows new
providers/connectors to be added without modifying existing code.
"""
