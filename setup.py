from setuptools import setup, find_namespace_packages

setup(
    name="hparams",
    version="0.3.1",
    packages=['hparams', 'hparams.localconfig'],
    include_package_data=True,
    install_requires=[],
    extras_require={
        'gcs': ['gcsfs'],
    },
    zip_safe=False
)
