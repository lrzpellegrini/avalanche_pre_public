################################################################################
# Copyright (c) 2021 ContinualAI.                                              #
# Copyrights licensed under the MIT License.                                   #
# See the accompanying LICENSE file for terms.                                 #
#                                                                              #
# Date: 24-06-2020                                                             #
# Author(s): Gabriele Graffieti                                                #
# E-mail: contact@continualai.org                                              #
# Website: avalanche.continualai.org                                           #
################################################################################

from typing import Sequence, Optional
from os.path import expanduser
from torchvision.datasets import CIFAR10
from torchvision import transforms

from avalanche.benchmarks import nc_scenario, NCScenario
from avalanche.benchmarks.utils import train_eval_avalanche_datasets

_default_cifar10_train_transform = transforms.Compose([
    transforms.RandomCrop(32, padding=4),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465),
                         (0.2023, 0.1994, 0.2010))
])

_default_cifar10_eval_transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465),
                         (0.2023, 0.1994, 0.2010))
])


def SplitCIFAR10(n_experiences: int,
                 first_exp_with_half_classes: bool = False,
                 return_task_id=False,
                 seed: Optional[int] = None,
                 fixed_class_order: Optional[Sequence[int]] = None,
                 train_transform=_default_cifar10_train_transform,
                 eval_transform=_default_cifar10_eval_transform) -> NCScenario:
    """
    Creates a CL scenario using the CIFAR10 dataset.
    If the dataset is not present in the computer the method automatically
    download it and store the data in the data folder.

    :param n_experiences: The number of experiences in the current scenario.
        The value of this parameter should be a divisor of 10 if
        first_task_with_half_classes is False, a divisor of 5 otherwise.
    :param first_exp_with_half_classes: A boolean value that indicates if a
        first pretraining step containing half of the classes should be used.
        If it's True, the first experience will use half of the classes (5 for
        cifar10). If this parameter is False, no pretraining step will be
        used and the dataset is simply split into a the number of experiences
        defined by the parameter n_experiences. Defaults to False.
    :param return_task_id: if True, a progressive task id is returned for every
        experience. If False, all experiences will have a task ID of 0.
    :param seed: A valid int used to initialize the random number generator.
        Can be None.
    :param fixed_class_order: A list of class IDs used to define the class
        order. If None, value of ``seed`` will be used to define the class
        order. If not None, the ``seed`` parameter will be ignored.
        Defaults to None.
    :param train_transform: The transformation to apply to the training data,
        e.g. a random crop, a normalization or a concatenation of different
        transformations (see torchvision.transform documentation for a
        comprehensive list of possible transformations).
        If no transformation is passed, the default train transformation
        will be used.
    :param eval_transform: The transformation to apply to the test data,
        e.g. a random crop, a normalization or a concatenation of different
        transformations (see torchvision.transform documentation for a
        comprehensive list of possible transformations).
        If no transformation is passed, the default eval transformation
        will be used.

    :returns: A properly initialized :class:`NCScenario` instance.
    """
    cifar_train, cifar_test = _get_cifar10_dataset(
        train_transform, eval_transform)

    if return_task_id:
        return nc_scenario(
            train_dataset=cifar_train,
            test_dataset=cifar_test,
            n_experiences=n_experiences,
            task_labels=True,
            seed=seed,
            fixed_class_order=fixed_class_order,
            per_exp_classes={0: 5} if first_exp_with_half_classes else None,
            class_ids_from_zero_in_each_exp=True)
    else:
        return nc_scenario(
            train_dataset=cifar_train,
            test_dataset=cifar_test,
            n_experiences=n_experiences,
            task_labels=False,
            seed=seed,
            fixed_class_order=fixed_class_order,
            per_exp_classes={0: 5} if first_exp_with_half_classes else None)


def _get_cifar10_dataset(train_transformation, eval_transformation):
    train_set = CIFAR10(expanduser("~") + "/.avalanche/data/cifar10/",
                        train=True, download=True)

    test_set = CIFAR10(expanduser("~") + "/.avalanche/data/cifar10/",
                       train=False, download=True)

    return train_eval_avalanche_datasets(
        train_set, test_set, train_transformation, eval_transformation)


__all__ = [
    'SplitCIFAR10'
]
