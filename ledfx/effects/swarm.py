import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import GradientEffect
from ledfx.effects.twod import Twod


class Swarm(Twod, GradientEffect):
    NAME = "Swarm"
    CATEGORY = "Matrix"

    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["test", "diag", "dump", "rotate"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys())),
            vol.Optional(
                "number_of_birds",
                description="Number of birds in the simulation",
                default=10,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=200)),
            vol.Optional(
                "bird_velocity",
                description="Velocity of the birds",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=5)),
            vol.Optional(
                "audio_reactive",
                description="Enable audio reactive mode",
                default=False,
            ): bool,
            vol.Optional(
                "predator",
                description="Enable predator",
                default=False,
            ): bool,
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.power_func = self.POWER_FUNCS_MAPPING[
            self._config["frequency_range"]
        ]

    def do_once(self):
        super().do_once()
        self.simulation = FiniteVolumeSimulation(
            self.r_width,
            self.r_height,
            num_birds=self._config["number_of_birds"],
            bird_velocity=self._config["bird_velocity"],
            angle_fluctuation=0.5,
            interaction_radius=1,
            predator_enabled=self._config["predator"],
        )
        self.simulation_matrix = np.zeros(
            (self.r_width, self.r_height, 3), dtype=np.uint8
        )

    def audio_data_updated(self, data):
        if self._config["audio_reactive"]:
            # Adjust bird velocity based on overall power
            power = getattr(data, self.power_func)() * 2
            speed_multiplier = max(
                1, self._config["bird_velocity"] * (power * 2)
            )
            self.simulation.bird_velocity = speed_multiplier
            self.simulation.predator_velocity = speed_multiplier - 0.5

            # Adjust angle fluctuation based on pitch
            pitch = data.pitch()

            # convert pitch into radian
            pitch = pitch * np.pi / 180

            self.simulation.angle_fluctuation = pitch
            # # flip the flock direction when there is a beat
            if data.onset():
                theta = (
                    2 * np.pi * np.random.rand(self.simulation.num_birds, 1)
                )
                self.simulation.bird_velocities_x = (
                    self.simulation.bird_velocity * np.cos(theta)
                )
                self.simulation.bird_velocities_y = (
                    self.simulation.bird_velocity * np.sin(theta)
                )
                # flip the predator direction when there is a beat
                if self.simulation.predator_enabled:
                    # generate a random angle for the predator
                    theta = 2 * np.pi * np.random.rand(1)
                    self.simulation.predator_velocity_x = (
                        self.simulation.predator_velocity * np.cos(theta)
                    )
                    self.simulation.predator_velocity_y = (
                        self.simulation.predator_velocity * np.sin(theta)
                    )

    def draw(self):
        self.simulation.step()
        self.roll_gradient()

        # Fade the entire bird_matrix by 10%
        self.simulation_matrix = (
            (self.simulation_matrix * 0.9).clip(0, 255).astype(int)
        )

        # Calculate the velocities for all birds
        velocities = np.sqrt(
            self.simulation.bird_velocities_x**2
            + self.simulation.bird_velocities_y**2
        )

        # Normalize the velocities to the range [0, 1]
        normalized_velocities = velocities / velocities.max()

        # Get the gradient colors based on the normalized velocities
        colors = self.get_gradient_color_vectorized(
            normalized_velocities.reshape(1, -1)
        )

        # Draw the current bird positions
        for i in range(self.simulation.num_birds):
            x = int(self.simulation.bird_positions_x[i])
            y = int(self.simulation.bird_positions_y[i])

            # Get the color for this bird
            color = colors[0, i]

            self.simulation_matrix[x, y] = color
        # Draw the predator
        if self.simulation.predator_enabled:
            predator_x = int(self.simulation.predator_position_x)
            predator_y = int(self.simulation.predator_position_y)

            self.simulation_matrix[predator_x, predator_y] = [255, 255, 255]

        # Draw the pixel data onto the image
        for x in range(self.matrix.width):
            for y in range(self.matrix.height):
                self.matrix.putpixel(
                    (x, y), tuple(self.simulation_matrix[x, y])
                )


class FiniteVolumeSimulation:
    """
    A class to represent a finite volume simulation.

    ...

    Attributes
    ----------
    box_width : float
        The width of the simulation box.
    box_height : float
        The height of the simulation box.
    num_birds : int
        The number of birds in the simulation.
    bird_velocity : float
        The velocity of the birds.
    angle_fluctuation : float
        The random fluctuation in bird direction (in radians).
    interaction_radius : float
        The radius within which birds interact with each other.
    time_step : float
        The time step for the simulation.

    Methods
    -------
    step():
        Performs a single step of the simulation.
    """

    def __init__(
        self,
        box_width,
        box_height,
        num_birds=10,
        bird_velocity=1.0,
        angle_fluctuation=0.5,
        interaction_radius=1,
        time_step=0.2,
        predator_enabled: bool = False,
    ):
        """
        Constructs all the necessary attributes for the finite volume simulation object.

        Parameters
        ----------
            box_width : float
                The width of the simulation box.
            box_height : float
                The height of the simulation box.
            num_birds : int
                The number of birds in the simulation.
            bird_velocity : float
                The velocity of the birds.
            angle_fluctuation : float
                The random fluctuation in bird direction (in radians).
            interaction_radius : float
                The radius within which birds interact with each other.
            time_step : float
                The time step for the simulation.
            predator_enabled : bool
                Whether or not to enable the predator.
        """
        self.predator_enabled = predator_enabled
        self.box_width = box_width
        self.box_height = box_height
        self.num_birds = num_birds
        self.initial_num_birds = num_birds
        self.bird_velocity = bird_velocity
        self.initial_bird_velocity = bird_velocity
        self.angle_fluctuation = angle_fluctuation
        self.initial_angle_fluctation = angle_fluctuation
        self.interaction_radius = interaction_radius
        self.initial_interaction_radius = interaction_radius
        self.time_step = time_step

        self.bird_positions_x = (
            np.random.rand(self.num_birds, 1) * self.box_width
        )
        self.bird_positions_y = (
            np.random.rand(self.num_birds, 1) * self.box_height
        )

        theta = 2 * np.pi * np.random.rand(self.num_birds, 1)
        self.bird_velocities_x = self.bird_velocity * np.cos(theta)
        self.bird_velocities_y = self.bird_velocity * np.sin(theta)

        if self.predator_enabled:
            self.predator_position_x = self.box_width / 2
            self.predator_position_y = self.box_height / 2

            # Initialize predator velocity
            self.predator_velocity = self.bird_velocity - 0.5
            self.predator_velocity_x = 0
            self.predator_velocity_y = 0

    def step(self):
        """
        Update the positions and velocities of the birds in the swarm.

        This method calculates the new positions and velocities of the birds based on their current positions, velocities,
        and the interaction rules of the swarm. It also handles the avoidance behavior when a predator is present.
        Args:
            None
        Returns:
            None
        """
        self.bird_positions_x += self.bird_velocities_x * self.time_step
        self.bird_positions_y += self.bird_velocities_y * self.time_step

        self.bird_positions_x = self.bird_positions_x % self.box_width
        self.bird_positions_y = self.bird_positions_y % self.box_height

        mean_theta = np.arctan2(self.bird_velocities_y, self.bird_velocities_x)
        for b in range(self.num_birds):
            neighbors = (
                self.bird_positions_x - self.bird_positions_x[b]
            ) ** 2 + (
                self.bird_positions_y - self.bird_positions_y[b]
            ) ** 2 < self.interaction_radius**2
            sx = np.sum(np.cos(mean_theta[neighbors]))
            sy = np.sum(np.sin(mean_theta[neighbors]))
            mean_theta[b] = np.arctan2(sy, sx)

            # If there are neighbors within the interaction radius, gradually adjust direction towards the mean direction of the neighbors
            if np.any(neighbors):
                target_theta = np.arctan2(
                    np.mean(self.bird_velocities_y[neighbors]),
                    np.mean(self.bird_velocities_x[neighbors]),
                )
                mean_theta[b] += (
                    target_theta - mean_theta[b]
                ) * 0.1  # Adjust the 0.1 value to change the rate of direction change

        theta = mean_theta + self.angle_fluctuation * (
            np.random.rand(self.num_birds, 1) - 0.5
        )

        self.bird_velocities_x = self.bird_velocity * np.cos(theta)
        self.bird_velocities_y = self.bird_velocity * np.sin(theta)

        # Birds avoid the predator
        if self.predator_enabled:
            predator_interaction_radius = self.interaction_radius * 2
            for b in range(self.num_birds):
                dx = self.bird_positions_x[b] - self.predator_position_x
                dy = self.bird_positions_y[b] - self.predator_position_y
                distance = dx**2 + dy**2

                if distance < predator_interaction_radius**2:
                    theta = np.arctan2(dy, dx) + np.pi
                    self.bird_velocities_x[b] = -self.bird_velocity * np.cos(
                        theta
                    )
                    self.bird_velocities_y[b] = -self.bird_velocity * np.sin(
                        theta
                    )

            self.update_predator()

    def update_predator(self):
        """
        Update the position and velocity of the predator based on the positions of the birds.

        This method calculates the nearest bird to the predator and updates the predator's position and velocity accordingly.
        If the predator reaches the bird, it "kills" the bird and spawns a new one at a safe distance from the predator.

        Args:
            None

        Returns:
            None
        """
        # Find the nearest bird
        distances = np.sqrt(
            (self.bird_positions_x - self.predator_position_x) ** 2
            + (self.bird_positions_y - self.predator_position_y) ** 2
        )
        nearest_bird_index = np.argmin(distances)
        # If the predator has reached the bird, "kill" the bird and spawn a new one
        if (
            distances[nearest_bird_index]
            < self.predator_velocity * self.time_step
        ):
            # Calculate a position that is at a certain distance from the predator in a direction towards the center of the box
            safe_distance = (
                self.predator_velocity * self.time_step * 10
            )  # Adjust this value as needed
            direction_to_center = np.arctan2(
                self.box_height / 2 - self.predator_position_y,
                self.box_width / 2 - self.predator_position_x,
            )
            new_bird_position_x = (
                self.predator_position_x
                + safe_distance * np.cos(direction_to_center)
            )
            new_bird_position_y = (
                self.predator_position_y
                + safe_distance * np.sin(direction_to_center)
            )

            # Ensure the new position is within the bounds of the box
            new_bird_position_x = min(
                max(new_bird_position_x, 0), self.box_width - 1
            )
            new_bird_position_y = min(
                max(new_bird_position_y, 0), self.box_height - 1
            )

            self.bird_positions_x[nearest_bird_index] = new_bird_position_x
            self.bird_positions_y[nearest_bird_index] = new_bird_position_y
            self.bird_velocities_x[nearest_bird_index] = (
                np.random.rand() - 0.5
            ) * self.bird_velocity
            self.bird_velocities_y[nearest_bird_index] = (
                np.random.rand() - 0.5
            ) * self.bird_velocity
        else:
            # Update predator's direction to chase the nearest bird
            dx = (
                self.bird_positions_x[nearest_bird_index]
                - self.predator_position_x
            )
            dy = (
                self.bird_positions_y[nearest_bird_index]
                - self.predator_position_y
            )
            theta = np.arctan2(dy, dx)

            self.predator_velocity_x = self.predator_velocity * np.cos(theta)
            self.predator_velocity_y = self.predator_velocity * np.sin(theta)

        # Update predator's position
        self.predator_position_x += self.predator_velocity_x * self.time_step
        self.predator_position_y += self.predator_velocity_y * self.time_step

        # Ensure predator's position is within the bounds of the box
        self.predator_position_x = min(
            max(self.predator_position_x, 0), self.box_width - 1
        )
        self.predator_position_y = min(
            max(self.predator_position_y, 0), self.box_height - 1
        )
