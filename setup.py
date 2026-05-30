#!/usr/bin/env python3
"""
URA - Universal Reasoning Assistant
Setup script for installation
"""

from setuptools import find_packages, setup


# Read requirements.txt
def read_requirements():
    with open("requirements.txt") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


# Read README.md
def read_readme():
    with open("README.md", encoding="utf-8") as f:
        return f.read()


setup(
    name="ura-assistant",
    version="2.0.0",
    description="Universal Reasoning Assistant - AI system with 3-layer security architecture",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="URA Development Team",
    python_requires=">=3.8",
    packages=find_packages(),
    install_requires=read_requirements(),
    entry_points={
        "console_scripts": [
            "ura=main_final:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["config/*.json", "config/*.txt", "core/data/*.json"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="AI assistant security privacy ollama",
    project_urls={
        "Documentation": "https://github.com/yourusername/ura-assistant",
        "Source": "https://github.com/yourusername/ura-assistant",
        "Tracker": "https://github.com/yourusername/ura-assistant/issues",
    },
)
