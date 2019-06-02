# encoding=UTF-8
#
# MIT License
#
# Copyright (c) 2018 Pedro Burón
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# https://github.com/pedroburon/dotenv
#
from __future__ import with_statement


__version__ = '0.0.5'


class Dotenv(dict):
    def __init__(self, file_path):
        self.file_path = file_path
        super(Dotenv, self).__init__(**self.__create_dict())

    def __create_dict(self):
        with open(self.file_path, 'r') as dotenv:
            variables = {}
            for line in dotenv.readlines():
                variables.update(self.__parse_line(line))
            return variables

    def __parse_line(self, line):
        if line.lstrip().startswith('#'):
            # discard and return nothing
            return {}
        if line.lstrip():
            # find the second occurence of a quote mark:
            quote_delimit = max(line.find('\'', line.find('\'') + 1),
                                line.find('"', line.rfind('"')) + 1)
            # find first comment mark after second quote mark
            comment_delimit = line.find('#', quote_delimit)
            line = line[:comment_delimit]
            key, value = map(lambda x: x.strip().strip('\'').strip('"'),
                             line.split('=', 1))
            return {key: value}
        else:
            return {}

    def __persist(self):
        with open(self.file_path, 'w') as dotenv:
            for key, value in self.items():
                dotenv.write("%s=%s\n" % (key, value))

    def __setitem__(self, key, value):
        super(Dotenv, self).__setitem__(key, value)
        self.__persist()

    def __delitem__(self, key):
        super(Dotenv, self).__delitem__(key)
        self.__persist()


def set_variable(file_path, key, value):
    dotenv = Dotenv(file_path)
    dotenv[key] = value


def get_variable(file_path, key):
    dotenv = Dotenv(file_path)
    return dotenv[key]


def get_variables(file_path):
    return Dotenv(file_path)
