from setuptools import setup, find_packages

setup(
    name="twiggy",
    version="1.0.0",
    description="CLI tool to generate real-time directory structure for Cursor AI",
    author="Maze",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "cursor_context": [
            "templates/*.template",
            "templates/*.mdc.template",
        ]
    },
    install_requires=[
        "click>=8.0.0",
        "watchdog>=3.0.0",
        "colorama>=0.4.0",
        "pyyaml>=6.0",
        "tree-sitter>=0.23.0",
        "tree-sitter-typescript>=0.23.0",
        "tree-sitter-javascript>=0.23.0",
    ],
    entry_points={
        "console_scripts": [
            "twiggy=cursor_context.cli:main",
        ],
    },
    python_requires=">=3.7",
)
