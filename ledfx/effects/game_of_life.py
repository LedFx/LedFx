import logging
import random
from enum import Enum

import numpy as np
import voluptuous as vol
from PIL import Image

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class HealthOptions(Enum):
    ALL = "All"
    DEAD = "Dead"
    OSCILLATING = "Oscillating"
    NONE = "None"


class GameOfLifeVisualiser(Twod):
    NAME = "Game of Life"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["gradient", "gradient_roll"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + [
        "health_check_interval",
        "frequency_range",
        "impulse_decay",
    ]
    HEALTH_CHECK_OPTIONS_VALUES = {
        HealthOptions.ALL.value: {
            HealthOptions.DEAD.value: True,
            HealthOptions.OSCILLATING.value: True,
        },
        HealthOptions.DEAD.value: {
            HealthOptions.DEAD.value: True,
            HealthOptions.OSCILLATING.value: False,
        },
        HealthOptions.OSCILLATING.value: {
            HealthOptions.DEAD.value: False,
            HealthOptions.OSCILLATING.value: True,
        },
        HealthOptions.NONE.value: {
            HealthOptions.DEAD.value: False,
            HealthOptions.OSCILLATING.value: False,
        },
    }

    history = 5
    # need history plus one colors

    dead_colors = np.array(
        [
            [180, 0, 0],
            [120, 0, 0],
            [60, 0, 0],
            [30, 0, 0],
            [15, 0, 0],
            [0, 0, 0],
        ],
        dtype=np.uint8,
    )

    live_colors = np.array(
        [
            [0, 180, 0],
            [0, 255, 0],
            [255, 255, 255],
            [200, 200, 200],
            [150, 150, 150],
            [100, 100, 100],
        ],
        dtype=np.uint8,
    )

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "health_checks",
                description="Check for and correct common unhealthy states",
                default=HealthOptions.ALL.value,
            ): vol.In([option.value for option in HealthOptions]),
            vol.Optional(
                "base_game_speed",
                description="Base number of steps per second to run",
                default=30,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            vol.Optional(
                "health_check_interval",
                description="Number of seconds between health checks",
                default=5,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
            vol.Optional(
                "frequency_range",
                description="Frequency range for life generation impulse",
                default="Lows (beat+bass)",
            ): vol.In(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys())),
            vol.Optional(
                "beat_inject",
                description="Generate entities on beat",
                default=True,
            ): bool,
            vol.Optional(
                "impulse_decay",
                description="Decay filter applied to the life generation impulse",
                default=0.05,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.1)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.onset = None
        self.last_health_check = self.EFFECT_START_TIME
        self.last_game_step = self.EFFECT_START_TIME

    def config_updated(self, config):
        super().config_updated(config)
        self.inject = config["beat_inject"]
        self.health_check_options = self.HEALTH_CHECK_OPTIONS_VALUES[
            config["health_checks"]
        ]
        self.base_game_speed = config["base_game_speed"]
        self.health_check_interval = config["health_check_interval"]
        if any(self.health_check_options.values()):
            self.check_health = True
        else:
            self.check_health = False
        self.power_func = self.POWER_FUNCS_MAPPING[
            self._config["frequency_range"]
        ]
        self.decay = config["impulse_decay"]
        self.impulse_filter = self.create_filter(
            alpha_decay=self.decay, alpha_rise=0.99
        )
        self.impulse = 0.0

    def do_once(self):
        super().do_once()
        self.game = GameOfLife(
            height=self.r_height, width=self.r_width, depth=self.history
        )
        if self.r_height <= 4 or self.r_width <= 4:
            _LOGGER.info(
                f"Board too small at {self.game.board_size} disabling beat injection of entities"
            )
            self.inject = False

    def audio_data_updated(self, data):
        if self.inject and data.volume_beat_now():
            self.game.add_random_entity()

        # if decay is set to minimum, then just run generations at full rate
        if self.decay == 0.01:
            self.impulse = 1.0
        else:
            self.impulse = self.impulse_filter.update(
                getattr(data, self.power_func)()
            )

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        self.check_board_health(self.current_time)
        self.step_board_if_time_elapsed(self.current_time)
        self.update_image_with_board()

    def check_board_health(self, current_time):
        """
        Checks the health of the game board and performs necessary actions based on the health check options.

        Args:
            current_time (float): The current time in seconds.

        Returns:
            None
        """
        if (
            self.check_health
            and current_time - self.last_health_check
            >= self.health_check_interval
        ):
            if self.health_check_options[HealthOptions.DEAD.value]:
                self.game.check_board_life()
            if self.health_check_options[HealthOptions.OSCILLATING.value]:
                self.game.check_board_oscillating()

            self.last_health_check = current_time

    def step_board_if_time_elapsed(self, current_time):
        """
        Steps the game board if the specified time has elapsed since the last step.

        Args:
            current_time (float): The current time in seconds.

        Returns:
            None
        """
        if (
            self.impulse > 0
            and current_time - self.last_game_step
            >= 1 / self.impulse / self.base_game_speed
        ):
            self.game.step_board()
            self.last_game_step = current_time

    def update_image_with_board(self):
        """
        Updates the image with the current game board using vectorization for improved performance.
        """

        # Convert PIL image to NumPy array for processing
        img_array = np.array(self.matrix)

        # Use game board and history directly
        current_board = self.game.board
        history_stack = np.array(self.game.board_history)

        # Calculate alive and dead durations using vectorization
        alive_durations = np.sum(history_stack, axis=0)
        dead_durations = np.sum(~history_stack, axis=0)

        # Map durations to colors using vectorized operations
        for duration in range(len(self.live_colors)):
            alive_mask = np.logical_and(
                current_board, alive_durations == duration
            )
            img_array[alive_mask] = self.live_colors[duration]

        for duration in range(len(self.dead_colors)):
            # where pixel is long dead, don't draw black, allows any image
            # behind to show through, and well as faster for all non plots
            if duration == 5:
                continue

            dead_mask = np.logical_and(
                ~current_board, dead_durations == duration
            )
            img_array[dead_mask] = self.dead_colors[duration]

        # Convert the NumPy array back to PIL Image and update self.matrix
        self.matrix = Image.fromarray(img_array)


class GameOfLife:
    """
    Represents the Game of Life simulation.

    Attributes:
        board_history (list): A list to store the history of the game boards.
        board_size (array): the board height and width
        board (np array): the matrix that stores cell values
        last_history_clear (time): the time of the last history clear

    Methods:
        initialize_board(): Initializes the game board with random cell states.
        step_board(board): Performs one step of the game simulation.
        board_is_dead(): Checks if the game board has reached a dead state.
        board_is_oscillating(lookback_generations): Checks if the game board is oscillating.
        update_image_with_board(image, board): Updates the image with the current game board.
        cleanup_board_history(): Clears the history of the game boards.
        add_glider(board): Generates a glider somewhere on the board.
        add_blinker(board): Generates a blinker somewhere on the board.
        add_toad(board): Generates a toad somewhere on the board.
        add_beacon(board): Generates a beacon somewhere on the board.
        add_random_entity(board): Generates a random entity on the board.
    """

    def __init__(self, height, width, depth):
        self.depth = depth
        self.board_size = [height, width]
        self.board = self.random_board()
        self.empty_board_history()
        _LOGGER.info("Universe invented 🌌")

    def random_board(self):
        """
        Return a board with random cell states.

        Returns:
            numpy.ndarray: The random game board.
        """
        _LOGGER.info("Evolving life")
        return np.random.choice([True, False], size=self.board_size)

    def step_board(self):
        """
        Performs one step of the game simulation.
        """
        # Update board_history
        self.board_history.append(np.copy(self.board))
        if len(self.board_history) > self.depth:
            self.board_history.pop(0)

        neighbors = sum(
            np.roll(np.roll(self.board, i, 0), j, 1)
            for i in (-1, 0, 1)
            for j in (-1, 0, 1)
            if (i != 0 or j != 0)
        )
        self.board = (neighbors == 3) | (self.board & (neighbors == 2))
        return self.board

    def check_board_life(self):
        """
        Checks if the game board has reached a dead state.

        Returns:
            bool: True if the game board is dead, False otherwise.
        """
        if len(self.board_history) < 2:
            return False
        current_board = self.board_history[-2]
        previous_board = self.board_history[-1]
        if np.array_equal(current_board, previous_board):
            _LOGGER.info("Board has died")
            self.empty_board_history()
            self.board = self.random_board()
            return True
        return False

    def check_board_oscillating(self, lookback_generations=5):
        """
        Checks if the game board is oscillating.

        Args:
            lookback_generations (int): The number of previous generations to look back.

        Returns:
            bool: True if the game board is oscillating, False otherwise.
        """
        if len(self.board_history) < lookback_generations:
            return False
        lookback_boards = self.board_history[-lookback_generations:]
        last_board = lookback_boards[-1]
        for i in range(len(lookback_boards) - 1):  # Exclude the last board
            if np.array_equal(lookback_boards[i], last_board):
                _LOGGER.info("Board is oscillating")
                self.empty_board_history()
                self.board = self.random_board()
                return True
        return False

    def empty_board_history(self):
        """
        Clears the board history.
        """
        _LOGGER.info("Erasing history of the universe")
        self.board_history = [
            np.zeros(self.board_size, dtype=bool) for _ in range(self.depth)
        ]

    def add_glider(self):
        """
        Generates a glider somewhere on the board
        """
        glider = np.array([[0, 0, 1], [1, 0, 1], [0, 1, 1]])
        rows, cols = self.board_size
        start_row = np.random.randint(0, rows - 3)
        start_col = np.random.randint(0, cols - 3)
        self.board[start_row : start_row + 3, start_col : start_col + 3] = (
            glider
        )
        _LOGGER.debug(f"Added glider at: {start_row}x{start_col}")

    def add_blinker(self):
        """
        Generates a blinker somewhere on the board
        """
        blinker = np.array([[1, 1, 1]])
        rows, cols = self.board_size
        start_row = np.random.randint(0, rows - 1)
        start_col = np.random.randint(0, cols - 3)
        self.board[start_row, start_col : start_col + 3] = blinker
        _LOGGER.debug(f"Added blinker at: {start_row}x{start_col}")

    def add_toad(self):
        """
        Generates a toad somewhere on the board
        """
        toad = np.array([[0, 1, 1, 1], [1, 1, 1, 0]])
        rows, cols = self.board_size
        start_row = np.random.randint(0, rows - 2)
        start_col = np.random.randint(0, cols - 4)
        self.board[start_row : start_row + 2, start_col : start_col + 4] = toad
        _LOGGER.debug(f"Added toad at: {start_row}x{start_col}")

    def add_beacon(self):
        """
        Generates a beacon somewhere on the board
        """
        beacon = np.array(
            [[1, 1, 0, 0], [1, 1, 0, 0], [0, 0, 1, 1], [0, 0, 1, 1]]
        )
        rows, cols = self.board_size
        start_row = np.random.randint(0, rows - 4)
        start_col = np.random.randint(0, cols - 4)
        self.board[start_row : start_row + 4, start_col : start_col + 4] = (
            beacon
        )
        _LOGGER.debug(f"Added beacon at: {start_row}x{start_col}")

    def add_random_entity(self):
        """
        Generates a random entity on the board
        """
        entities = [
            self.add_glider,
            self.add_blinker,
            self.add_toad,
            self.add_beacon,
        ]
        random_entity = random.choice(entities)
        random_entity()
