"""Import allow-list for free-form transform_frame / custom_plot runners."""

ALLOWED_MODULES = frozenset(
    {
        "pandas",
        "numpy",
        "matplotlib",
        "matplotlib.pyplot",
        "math",
        "re",
        "datetime",
        "collections",
        "itertools",
        "json",
        "pathlib",
    }
)

# Present in the image for fixed tools only. Free-form code must not import these.
BLOCKED_FOR_FREEFORM = frozenset(
    {
        "scipy",
        "statsmodels",
        "sklearn",
        "scikit-learn",
        "requests",
        "urllib",
        "http",
        "socket",
        "subprocess",
        "ctypes",
        "multiprocessing",
    }
)


def is_import_allowed(module_name: str) -> bool:
    root = module_name.split(".", 1)[0]
    if root in BLOCKED_FOR_FREEFORM or module_name in BLOCKED_FOR_FREEFORM:
        return False
    return module_name in ALLOWED_MODULES or root in ALLOWED_MODULES
