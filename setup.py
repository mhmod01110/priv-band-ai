# setup.py
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="legal-policy-analyzer",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="محلل الامتثال القانوني للمتاجر الإلكترونية",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/legal-policy-analyzer",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "fastapi>=0.104.1",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.5.0",
        "python-dotenv>=1.0.0",
        "openai>=1.3.0",
        "python-multipart>=0.0.6",
        "jinja2>=3.1.2",
        "aiofiles>=23.2.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "httpx>=0.25.1",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "legal-analyzer=app.main:app",
        ],
    },
)