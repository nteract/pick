#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from mock import Mock, patch

from .. import subkernels
from .. import exceptions


class TestSubkernelRegistration(unittest.TestCase):
    def setUp(self):
        self.subkernels = subkernels.Subkernels()

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

    def test_registering_entry_points(self):
        fake_entrypoint = Mock(load=Mock())
        fake_entrypoint.name = "fake-subkernel"

        with patch(
            "entrypoints.get_group_all", return_value=[fake_entrypoint]
        ) as mock_get_group_all:

            self.subkernels.register_entry_points()
            mock_get_group_all.assert_called_once_with("pick_kernel.subkernel")
            self.assertEqual(
                self.subkernels.get_subkernel("fake-subkernel"),
                fake_entrypoint.load.return_value,
            )
