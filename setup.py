from setuptools import setup, find_packages

setup(
    name="btcracker",
    version="0.1.0",
    description="Bitcoin wallet password recovery tool",
    author="BTCracker Team",
    packages=find_packages(),
    python_requires=">=3.6",
    install_requires=[
        "pywallet",
        # Optional dependencies (commented out):
        # "tqdm",  # For progress bar
        # Optional external tools:
        # - hashcat (external)
        # - john (external)
    ],
    entry_points={
        "console_scripts": [
            "btcracker=btcracker.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
) 