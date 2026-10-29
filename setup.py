from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="virtual-earth-language",
    version="0.1.0",
    author="Alethevia",
    description="Experimental spatial simulation and explicit symbol communication",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Alethevia/virtual-earth-language",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.11",
    install_requires=[
        "torch>=2.0.0",
        "numpy>=1.21.0",
        "pandas>=1.3.0",
        "matplotlib>=3.5.0",
        "wandb>=0.12.0",
        "hydra-core>=1.1.0",
        "gymnasium>=0.26.0",
        "stable-baselines3>=1.6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.2.0",
            "pytest-cov>=2.12.0",
            "black>=21.0.0",
            "flake8>=3.9.0",
            "mypy>=0.910",
        ],
        "viz": [
            "plotly>=5.0.0",
            "seaborn>=0.11.0",
            "tensorboard>=2.8.0",
        ],
        "web": [
            "fastapi>=0.68.0",
            "uvicorn>=0.15.0",
            "websockets>=10.0",
        ],
        "gpu": [
            "torch",
        ],
    },
)
