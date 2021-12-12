from setuptools import setup, find_packages

from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

requirements = [
    'PyYAML',
    'jinja2',
    'ipython>=1.0',
]

setup(
    name="jinja-yaml-magic",
    version="0.2.0a1",
    packages=find_packages(),

    # package_data={
    #     '': ['*.txt']
    # },

    author="Jay Carlson",
    author_email="nop@nop.com",
    description="Support Jinja2 and YAML in IPython/Jupyter notebooks",
    long_description=long_description,
    long_description_content_type='text/markdown',

    install_requires=requirements,

    extras_require={
        "ansible": ["ansible-core>=2.12.1"],
    },

    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 2",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],

    license="MIT",
    keywords=["jupyter", "ipython", "yaml", "jinja", "jinja2"],
    url='https://github.com/nopdotcom/jupyter-jinja-yaml-magic',

)
