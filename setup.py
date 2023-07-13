import os.path
import sys
from setuptools import setup, find_packages
from agoragym.version import VERSION

setup(name='AgoraGym',
      version=VERSION,
      description="AgoraGym: a rtc reinforcement learning simulation environment.",
      install_requires=[
          'gym',
          'numpy',
      ],
      packages=find_packages(),
      include_package_data=True,
      exclude_packge_data={'': ['.gitignore']}
      )
