def __getattr__(name):
    # Resolved from installed package metadata rather than hardcoded, so
    # pyproject.toml stays the single source of truth for the version. A
    # hardcoded constant here drifts silently: it still read 0.1.0 after 0.1.1
    # shipped.
    #
    # Looked up lazily because this module is imported by the detection hook on
    # every prompt, and reading package metadata walks site-packages. Only the
    # CLI asks for __version__, so the hook never pays for it.
    if name == "__version__":
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("aihsm")
        except PackageNotFoundError:
            # Running from a source checkout or the bundled plugin copy, where
            # aihsm was never pip-installed.
            return "0+unknown"
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
