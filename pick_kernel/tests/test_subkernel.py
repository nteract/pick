#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from mock import Mock

from .. import subkernel
from .. import exceptions


class TestSubkernelRegistration(unittest.TestCase):
    def setUp(self):
        self.subkernels = subkernel.Subkernels()

    def test_registration(self):
        mock_subkernel = Mock()
        self.subkernels.register("mock_subkernel", mock_subkernel)
        self.assertIn("mock_subkernel", self.subkernels._subkernels)
        self.assertIs(mock_subkernel, self.subkernels._subkernels["mock_subkernel"])

    def test_getting(self):
        mock_subkernel = Mock()
        self.subkernels.register("mock_subkernel", mock_subkernel)
        retrieved_subkernel = self.subkernels.get_subkernel("mock_subkernel")
        self.assertIs(mock_subkernel, retrieved_subkernel)

        self.assertRaises(
            exceptions.PickRegistrationException,
            self.subkernels.get_subkernel,
            "non-existent",
        )
