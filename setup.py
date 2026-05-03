"""
Setup script pour AttoVisio.
Permet l'installation via : pip install .
"""

from setuptools import setup, find_packages
import os

# Lire le README pour la description longue
here = os.path.abspath(os.path.dirname(__file__))
try:
    with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = "AttoVisio — Rend visibles les actions invisibles en informatique."

setup(
    name="attovisio",
    version="0.1.0",
    author="Attobra Prince",
    author_email="attobraprince@example.com",
    description="Rend visibles les actions invisibles en informatique : appels, fichiers, réseau, ressources, sécurité.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/attobraprince/attovisio",
    project_urls={
        "Bug Tracker": "https://github.com/attobraprince/attovisio/issues",
        "Documentation": "https://github.com/attobraprince/attovisio#readme",
        "Source": "https://github.com/attobraprince/attovisio",
    },
    packages=find_packages(exclude=["tests*", "examples*", "docs*"]),
    python_requires=">=3.8",
    install_requires=[
        # Aucune dépendance obligatoire !
        # psutil est optionnel (SystemMonitor, NetworkWatcher)
    ],
    extras_require={
        "full": [
            "psutil>=5.9.0",
        ],
        "dev": [
            "psutil>=5.9.0",
            "pytest>=7.0",
            "pytest-cov>=4.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Debuggers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Security",
        "Topic :: Education",
    ],
    keywords="tracing debugging monitoring security visualization observability pedagogy",
    include_package_data=True,
    zip_safe=False,
)
