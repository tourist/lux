#!/usr/bin/env python
# Script for running ${project_name} with lux
import lux


if __name__ == '__main__':
    lux.execute_from_config('${project_name}.settings')
