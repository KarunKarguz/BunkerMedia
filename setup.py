from setuptools import find_packages, setup


setup(
    name="bunkermedia",
    version="0.2.5",
    description="Self-hosted intelligent media acquisition and streaming system",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="BunkerMedia",
    python_requires=">=3.10",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    package_data={"bunkermedia": ["ui/*.html", "ui/*.css", "ui/*.js", "ui/*.webmanifest", "ui/*.svg"]},
    install_requires=[
        "fastapi>=0.115.0",
        "uvicorn>=0.30.0",
        "yt-dlp>=2025.1.1",
        "PyYAML>=6.0.2",
        "pydantic>=2.8.0",
        "httpx>=0.27.0",
    ],
    entry_points={
        "console_scripts": [
            "bunker=bunkermedia.cli:main",
        ]
    },
    license="MIT",
)
