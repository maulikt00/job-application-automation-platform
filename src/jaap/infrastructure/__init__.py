"""Infrastructure layer.

Concrete, swappable implementations of the interfaces defined in
application/interfaces: the real database, the real AI providers,
the real browser engine, the real website connectors, and
configuration loading. This is the only layer allowed to depend on
third-party SDKs and frameworks.
"""
