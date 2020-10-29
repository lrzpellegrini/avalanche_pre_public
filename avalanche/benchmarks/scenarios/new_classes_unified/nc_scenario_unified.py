################################################################################
# Copyright (c) 2020 ContinualAI Research                                      #
# Copyrights licensed under the CC BY 4.0 License.                             #
# See the accompanying LICENSE file for terms.                                 #
#                                                                              #
# Date: 12-05-2020                                                             #
# Author(s): Lorenzo Pellegrini                                                #
# E-mail: contact@continualai.org                                              #
# Website: clair.continualai.org                                               #
################################################################################

import torch
from typing import Sequence, List, Optional, Dict, Generic, Any

from avalanche.benchmarks.scenarios.generic_definitions import \
    TrainSetWithTargets, TestSetWithTargets, MTSingleSet
from avalanche.training.utils import TransformationSubset
from avalanche.benchmarks.scenarios.generic_cl_scenario import \
    GenericCLScenario, GenericStepInfo
from benchmarks.utils import grouped_and_ordered_indexes


class NCScenarioUnified(GenericCLScenario[TrainSetWithTargets,
                                          TestSetWithTargets,
                                          'NCUnifiedStepInfo'],
                        Generic[TrainSetWithTargets, TestSetWithTargets]):
    """
    # TODO: adapt doc (and helpers SIT vs MT)
    This class defines a "New Classes" scenario. It is used when creating both
    task-oriented and single-incremental-task (a.k.a. task-free) scenarios as
    it doesn't make any difference between them. Once created, an instance
    of this class can be iterated in order to obtain the step sequence
    under the form of instances of :class:`NCUnifiedStepInfo`.

    This class can be used directly. However, we recommend using facilities like
    :func:`.scenario_creation.create_nc_single_dataset_sit_scenario`,
    :func:`.scenario_creation.create_nc_single_dataset_multi_task_scenario`,
    :func:`.scenario_creation.create_nc_multi_dataset_sit_scenario` and
    :func:`.scenario_creation.create_nc_multi_dataset_multi_task_scenario`.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, train_dataset: TrainSetWithTargets,
                 test_dataset: TestSetWithTargets,
                 n_steps: int,
                 task_labels: bool,
                 shuffle: bool = True,
                 seed: Optional[int] = None,
                 fixed_class_order: Optional[Sequence[int]] = None,
                 per_step_classes: Optional[Dict[int, int]] = None,
                 class_ids_from_zero_from_first_step: bool = False,
                 class_ids_from_zero_in_each_step: bool = False,
                 reproducibility_data: Optional[Dict[str, Any]] = None):
        """
        # TODO: adapt doc
        Creates a NCGenericScenario instance given the training and test
        Datasets and the number of steps.

        By default, the number of classes will be automatically detected by
        looking at the training Dataset targets field. Classes will be
        uniformly distributed across the "n_steps" unless a per_step_classes
        argument is specified.

        The number of classes must be divisible without remainder by the number
        of steps. This also applies when the per_step_classes argument is not
        None.

        :param train_dataset: The training dataset. The dataset must contain a
            "targets" field. For instance, one can safely use the datasets from
            the torchvision package.
        :param test_dataset: The test dataset. The dataset must contain a
            "targets" field. For instance, one can safely use the datasets from
            the torchvision package.
        :param n_steps: The number of steps.
        :param task_labels: If True, each step will have an ascending task
            label. If False, the task label will be 0 for all the steps.
        :param shuffle: If True, the class order will be shuffled. Defaults to
            True.
        :param seed: If shuffle is True and seed is not None, the class order
            will be shuffled according to the seed. When None, the current
            PyTorch random number generator state will be used.
            Defaults to None.
        :param fixed_class_order: If not None, the class order to use (overrides
            the shuffle argument). Very useful for enhancing
            reproducibility. Defaults to None.
        :param per_step_classes: Is not None, a dictionary whose keys are
            (0-indexed) step IDs and their values are the number of classes
            to include in the respective steps. The dictionary doesn't
            have to contain a key for each step! All the remaining steps
            will contain an equal amount of the remaining classes. The
            remaining number of classes must be divisible without remainder
            by the remaining number of steps. For instance,
            if you want to include 50 classes in the first step
            while equally distributing remaining classes across remaining
            steps, just pass the "{0: 50}" dictionary as the
            per_step_classes parameter. Defaults to None.
        :param class_ids_from_zero_from_first_step: If True, original class IDs
            will be remapped so that they will appear as having an ascending
            order. For instance, if the resulting class order after shuffling
            (or defined by fixed_class_order) is [23, 34, 11, 7, 6, ...] and
            class_ids_from_zero_from_first_step is True, then all the patterns
            belonging to class 23 will appear as belonging to class "0",
            class "34" will be mapped to "1", class "11" to "2" and so on.
            This is very useful when drawing confusion matrices and when dealing
            with algorithms with dynamic head expansion. Defaults to False.
            Mutually exclusive with the class_ids_from_zero_in_each_step
            parameter.
        :param class_ids_from_zero_in_each_step: If True, original class IDs
            will be mapped to range [0, n_classes_in_step) for each step.
            Defaults to False. Mutually exclusive with the
            class_ids_from_zero_from_first_step parameter.
        :param reproducibility_data: If not None, overrides all the other
            scenario definition options. This is usually a dictionary containing
            data used to reproduce a specific experiment. One can use the
            ``get_reproducibility_data`` method to get (and even distribute)
            the experiment setup so that it can be loaded by passing it as this
            parameter. In this way one can be sure that the same specific
            experimental setup is being used (for reproducibility purposes).
            Beware that, in order to reproduce an experiment, the same train and
            test datasets must be used. Defaults to None.
        """
        if class_ids_from_zero_from_first_step and \
                class_ids_from_zero_in_each_step:
            raise ValueError('Invalid mutually exclusive options '
                             'class_ids_from_zero_from_first_step and '
                             'class_ids_from_zero_in_each_step set at the '
                             'same time')
        # TODO: adapt comments
        if reproducibility_data:
            n_steps = reproducibility_data['n_steps']

        if n_steps < 1:
            raise ValueError('Invalid number of steps (n_steps parameter): '
                             'must be greater than 0')

        self.classes_order: List[int] = []
        """ Stores the class order (remapped class IDs) """

        self.classes_order_original_ids: List[int] = torch.unique(
            torch.as_tensor(train_dataset.targets),
            sorted=True).tolist()  # TODO: remove in favour of class_mapping?
        """ Stores the class order (original class IDs) """

        n_original_classes = max(self.classes_order_original_ids) + 1

        self.class_mapping: List[int] = []
        """ class_mapping stores the class mapping so that
        mapped_class_id = class_mapping[original_class_id] """

        self.n_classes_per_step: List[int] = []
        """ A list that, for each step (identified by its index/ID),
            stores the number of classes assigned to that step """

        self.classes_in_step: List[List[int]] = []
        """ A list that, for each step (identified by its index/ID),
            stores a list of the (optionally remapped) IDs of classes assigned 
            to that step """

        self.class_ids_from_zero_from_first_step: bool = \
            class_ids_from_zero_from_first_step
        """ If True the class IDs have been remapped to start from zero """

        self.class_ids_from_zero_in_each_step: bool = \
            class_ids_from_zero_in_each_step
        """ If True the class IDs have been remapped to start from zero in 
        each step """

        # Note: if fixed_class_order is None and shuffle is False,
        # the class order will be the one encountered
        # By looking at the train_dataset targets field
        if reproducibility_data:
            self.classes_order_original_ids = \
                reproducibility_data['classes_order_original_ids']
            self.class_ids_from_zero_from_first_step = \
                reproducibility_data['class_ids_from_zero_from_first_step']
            self.class_ids_from_zero_in_each_step = \
                reproducibility_data['class_ids_from_zero_in_each_step']
        elif fixed_class_order is not None:
            # User defined class order -> just use it
            if len(set(self.classes_order_original_ids).union(
                    set(fixed_class_order))) != \
                    len(self.classes_order_original_ids):
                raise ValueError('Invalid classes defined in fixed_class_order')

            self.classes_order_original_ids = list(fixed_class_order)
        elif shuffle:
            # No user defined class order.
            # If a seed is defined, set the random number generator seed.
            # If no seed has been defined, use the actual
            # random number generator state.
            # Finally, shuffle the class list to obtain a random classes
            # order
            if seed is not None:
                torch.random.manual_seed(seed)
            self.classes_order_original_ids = \
                torch.as_tensor(self.classes_order_original_ids)[
                    torch.randperm(len(self.classes_order_original_ids))
                ].tolist()

        self.n_classes: int = len(self.classes_order_original_ids)
        """ The number of classes """

        if reproducibility_data:
            self.n_classes_per_step = \
                reproducibility_data['n_classes_per_step']
        elif per_step_classes is not None:
            # per_step_classes is a user-defined dictionary that defines
            # the number of classes to include in some (or all) steps.
            # Remaining classes are equally distributed across the other steps
            #
            # Format of per_step_classes dictionary:
            #   - key = step id
            #   - value = number of classes for this step

            if max(per_step_classes.keys()) >= n_steps or min(
                    per_step_classes.keys()) < 0:
                # The dictionary contains a key (that is, a step id) >=
                # the number of requested steps... or < 0
                raise ValueError(
                    'Invalid step id in per_step_classes parameter: '
                    'step ids must be in range [0, n_steps)')
            if min(per_step_classes.values()) < 0:
                # One or more values (number of classes for each step) < 0
                raise ValueError('Wrong number of classes defined for one or '
                                 'more steps: must be a non-negative value')

            if sum(per_step_classes.values()) > self.n_classes:
                # The sum of dictionary values (n. of classes for each step)
                # >= the number of classes
                raise ValueError('Insufficient number of classes: '
                                 'per_step_classes parameter can\'t '
                                 'be satisfied')

            # Remaining classes are equally distributed across remaining steps
            # This amount of classes must be be divisible without remainder by
            # the number of remaining steps
            remaining_steps = n_steps - len(per_step_classes)
            if remaining_steps > 0 and (self.n_classes - sum(
                    per_step_classes.values())) % remaining_steps > 0:
                raise ValueError('Invalid number of steps: remaining classes '
                                 'cannot be divided by n_steps')

            # default_per_step_classes is the default amount of classes
            # for the remaining steps
            if remaining_steps > 0:
                default_per_step_classes = (self.n_classes - sum(
                    per_step_classes.values())) // remaining_steps
            else:
                default_per_step_classes = 0

            # Initialize the self.n_classes_per_step list using
            # "default_per_step_classes" as the default
            # amount of classes per step. Then, loop through the
            # per_step_classes dictionary to set the customized,
            # user defined, classes for the required steps.
            self.n_classes_per_step = \
                [default_per_step_classes] * n_steps
            for step_id in per_step_classes:
                self.n_classes_per_step[step_id] = per_step_classes[step_id]
        else:
            # Classes will be equally distributed across the steps
            # The amount of classes must be be divisible without remainder
            # by the number of steps
            if self.n_classes % n_steps > 0:
                raise ValueError(
                    'Invalid number of steps: classes contained in dataset '
                    'cannot be divided by n_steps')
            self.n_classes_per_step = \
                [self.n_classes // n_steps] * n_steps

        # Before populating the classes_in_step list,
        # define the remapped class IDs.
        if reproducibility_data:
            # Method 0: use reproducibility data
            self.classes_order = reproducibility_data['classes_order']
            self.class_mapping = reproducibility_data['class_mapping']
        elif self.class_ids_from_zero_from_first_step:
            # Method 1: remap class IDs so that they appear in ascending order
            # over all steps
            self.classes_order = list(range(0, self.n_classes))
            self.class_mapping = [-1] * n_original_classes
            for class_id in range(self.n_classes):
                if class_id in self.classes_order_original_ids:
                    self.class_mapping[class_id] = \
                        self.classes_order_original_ids.index(class_id)
        elif self.class_ids_from_zero_in_each_step:
            # Method 2: remap class IDs so that they appear in range [0, N] in
            # each step
            self.classes_order = []
            self.class_mapping = [-1] * n_original_classes
            next_class_idx = 0
            for step_id, step_n_classes in self.n_classes_per_step:
                self.classes_order += list(range(step_n_classes))
                for step_class_idx in range(step_n_classes):
                    original_class_position = next_class_idx + step_class_idx
                    original_class_id = self.classes_order_original_ids[
                        original_class_position]
                    self.class_mapping[original_class_id] = step_class_idx
                next_class_idx += step_n_classes
        else:
            # Method 3: no remapping of any kind
            # remapped_id = class_mapping[class_id] -> class_id == remapped_id
            self.classes_order = self.classes_order_original_ids
            self.class_mapping = list(range(0, n_original_classes))

        self.train_dataset = TransformationSubset(
            train_dataset, None, class_mapping=self.class_mapping)
        self.test_dataset = TransformationSubset(
            test_dataset, None, class_mapping=self.class_mapping)

        # Populate the classes_in_step list
        # "classes_in_step[step_id]": list of class IDs assigned
        # to step "step_id"
        for step_id in range(n_steps):
            classes_start_idx = sum(self.n_classes_per_step[:step_id])
            classes_end_idx = classes_start_idx + self.n_classes_per_step[
                step_id]

            self.classes_in_step.append(
                self.classes_order[classes_start_idx:classes_end_idx])

        # Finally, create the step -> patterns assignment.
        # In order to do this, we don't load all the patterns
        # instead we use the targets field.
        train_steps_patterns_assignment = []
        test_steps_patterns_assignment = []
        for step_id in range(n_steps):
            selected_classes = set(self.classes_in_step[step_id])
            selected_indexes_train = []
            for idx, element in enumerate(self.train_dataset.targets):
                if element in selected_classes:
                    selected_indexes_train.append(idx)

            selected_indexes_test = []
            for idx, element in enumerate(self.test_dataset.targets):
                if element in selected_classes:
                    selected_indexes_test.append(idx)

            train_steps_patterns_assignment.append(selected_indexes_train)
            test_steps_patterns_assignment.append(selected_indexes_test)

        task_ids: List[int]
        if task_labels:
            task_ids = list(range(n_steps))
        else:
            task_ids = [0] * n_steps

        super(NCScenarioUnified, self).__init__(
            train_dataset,
            test_dataset,
            train_steps_patterns_assignment,
            test_steps_patterns_assignment,
            task_ids, step_factory=NCUnifiedStepInfo)

    def get_reproducibility_data(self):
        reproducibility_data = {
            'class_mapping': self.class_mapping,
            'n_classes_per_step': self.n_classes_per_step,
            'class_ids_from_zero_from_first_step': bool(
                self.class_ids_from_zero_from_first_step),
            'class_ids_from_zero_in_each_step': bool(
                self.class_ids_from_zero_in_each_step),
            'classes_order': self.classes_order,
            'classes_order_original_ids': self.classes_order_original_ids,
            'n_steps': int(self.n_steps)}
        return reproducibility_data

    def classes_in_step_range(self, step_start: int,
                              step_end: Optional[int] = None) -> List[int]:
        """
        Gets a list of classes contained in the given steps. The steps are
        defined by range. This means that only the classes in range
        [step_start, step_end) will be included.

        :param step_start: The starting step ID
        :param step_end: The final step ID. Can be None, which means that all
            the remaining steps will be taken.

        :returns: The classes contained in the required step range.
        """
        # Ref: https://stackoverflow.com/a/952952
        if step_end is None:
            return [
                item for sublist in
                self.classes_in_step[step_start:]
                for item in sublist]

        return [
            item for sublist in
            self.classes_in_step[step_start:step_end]
            for item in sublist]

    def get_class_split(self, step_id: int):
        if step_id >= 0:
            classes_in_this_step = \
                self.classes_in_step[step_id]
            previous_classes = self.classes_in_step_range(0, step_id)
            classes_seen_so_far = \
                previous_classes + classes_in_this_step
            future_classes = self.classes_in_step_range(step_id + 1)
        else:
            classes_in_this_step = []
            previous_classes = []
            classes_seen_so_far = []
            future_classes = self.classes_in_step_range(0)

        # Without explicit tuple parenthesis, PEP8 E127 occurs
        return (classes_in_this_step, previous_classes, classes_seen_so_far,
                future_classes)


class NCUnifiedStepInfo(GenericStepInfo[NCScenarioUnified[TrainSetWithTargets,
                                                          TestSetWithTargets]],
                        Generic[TrainSetWithTargets, TestSetWithTargets]):
    """
    # TODO: adapt doc
    Defines a "New Classes" step. It defines methods to obtain the current,
    previous, cumulative and future training and test sets. It also defines
    fields that can be used to check which classes are in this, previous and
    future steps. Instances of this class are usually created when iterating
    over a :class:`NCScenarioUnified` instance.

    It keeps a reference to that :class:`NCScenarioUnified`
    instance, which can be used to retrieve additional info about the
    scenario.
    """

    def __init__(self,
                 scenario: NCScenarioUnified[TrainSetWithTargets,
                                             TestSetWithTargets],
                 current_step: int,
                 force_train_transformations: bool = False,
                 force_test_transformations: bool = False,
                 are_transformations_disabled: bool = False):
        """
        # TODO: adapt doc
        Creates a NCUnifiedStepInfo instance given the root scenario.
        Instances of this class are usually created automatically while
        iterating over an instance of :class:`NCScenarioUnified`.

        :param scenario: A reference to the NC scenario
        :param current_step: The step ID
        :param force_train_transformations: If True, train transformations will
            be applied to the test set too. The ``force_test_transformations``
            parameter can't be True at the same time. Defaults to False.
        :param force_test_transformations: If True, test transformations will be
            applied to the training set too. The ``force_train_transformations``
            parameter can't be True at the same time. Defaults to False.
        :param are_transformations_disabled: If True, transformations are
            disabled. That is, patterns and targets will be returned as
            outputted by  the original training and test Datasets. Overrides
            ``force_train_transformations`` and ``force_test_transformations``.
            Defaults to False.
        """

        class_split = scenario.get_class_split(current_step)
        (classes_in_this_step, previous_classes, classes_seen_so_far,
         future_classes) = class_split

        super(NCUnifiedStepInfo, self).__init__(
            scenario, current_step, classes_in_this_step, previous_classes,
            classes_seen_so_far, future_classes,
            force_train_transformations=force_train_transformations,
            force_test_transformations=force_test_transformations,
            are_transformations_disabled=are_transformations_disabled,
            transformation_step_factory=NCUnifiedStepInfo)

    def _make_subset(self, is_train: bool, step: int, **kwargs) -> MTSingleSet:
        subset, t = super()._make_subset(is_train, step)

        subset = TransformationSubset(
            subset, None, class_mapping=self.scenario.class_mapping)

        return TransformationSubset(
            subset,
            grouped_and_ordered_indexes(
                subset.targets, None,
                **kwargs)), t


__all__ = ['NCScenarioUnified', 'NCUnifiedStepInfo']