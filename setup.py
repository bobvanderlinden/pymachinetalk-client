#!/usr/bin/env python

from distutils.core import setup

setup(name='pymachinetalk',
      version='1.0',
      description='Client library for Machinetalk',
      author='Bob van der Linden',
      author_email='bobvanderlinden@gmail.com',
      url='https://github.com/bobvanderlinden/pymachinetalk/',
      install_requires=[
          "machinekit_protobuf",
          "aiozmq",
          "zmq",
          "zeroconf"
      ],
      )
