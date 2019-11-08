# !/usr/bin/env python

from setuptools import setup

setup(name='midca',
      version='1.4',
      description='Metacognitive Integrated Dual-Cycle Architecture',
      author='Michael T. Cox and midca Lab',
      author_email='wsri-midca-help@wright.edu',
      install_requires=['numpy'],
      packages=['midca',
                'midca.domains',
                'midca.domains.genios',
                'midca.worldsim',
                'midca.examples',
                'midca.modules',
                'midca.modules._plan',
                'midca.modules._plan.asynch',
                'midca.modules._plan.jShop',
                'midca.modules.gens',
                'midca.metamodules'],

      package_data={'': ['*.jar', 'midca.modules._plan.jShop'],
                    '': ['*.*', 'midca.modules._plan.jShop'],
                    },
      )
