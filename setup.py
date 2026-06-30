from setuptools import setup, find_packages

setup(
    name="moneypulse",
    version="2.0.0",
    description="Official Money-Pulse Python SDK — Accept payments and process payouts across Africa.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="NOCYL-PULSE",
    author_email="dev@money-pulse.org",
    url="https://github.com/Nocyl/moneypulse-python",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=["requests>=2.25.0"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
