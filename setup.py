from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")


# get version from __version__ variable in ksa_zatca/__init__.py
from ksa_zatca import __version__ as version

setup(
	name="ksa_zatca",
	version=version,
	description="App to hold regional code for Saudi Arabia, built on top of ERPNext.",
	author="Trigger Solutions",
	author_email="",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
