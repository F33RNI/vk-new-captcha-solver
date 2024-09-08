"""
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org>
"""

import json
import logging
import os

import numpy as np
from cv2.typing import MatLike
from keras import Sequential, layers, losses, models
from numpy.typing import NDArray

INPUT_HEIGHT = 64
INPUT_WIDTH = 64
SAVE_DIR_DEFAULT = "model"


class Model:
    def __init__(self, from_path: str | None = None, labels: int = 0) -> None:
        """Compiles or loads model from file

        Args:
            from_path (str | None, optional): provide path to directory with model and labels map to load from them
            instead of compiling a new model
            labels (int): output classes (number of possible letters). Will be ignored if from_path provided

        Raises:
            Exception: in case of error
        """
        self.labels_map: list[str] = []
        if from_path:
            # Load labels map
            labels_map_path = os.path.join(from_path, "labels_map.json")
            logging.info(f"Loading labels map from {labels_map_path}")
            with open(labels_map_path, "r", encoding="utf-8") as labels_map_io:
                self.labels_map = json.load(labels_map_io)

            # Load model
            model_path = os.path.join(from_path, "model.keras")
            logging.info(f"Loading model from {model_path}")
            self.model: Sequential = models.load_model(model_path)  # pyright: ignore[reportAttributeAccessIssue]
            return

        # Create "empty" model
        if labels <= 0:
            raise Exception("labels must be > 0 or provide from_file")
        self.model = Sequential(
            [
                layers.Input(shape=(INPUT_HEIGHT, INPUT_WIDTH, 1)),
                layers.BatchNormalization(),
                layers.Conv2D(32, (3, 3), activation="relu"),
                layers.MaxPooling2D((2, 2)),
                layers.Conv2D(64, (3, 3), activation="relu"),
                layers.MaxPooling2D((2, 2)),
                layers.Conv2D(64, (3, 3), activation="relu"),
                layers.MaxPooling2D((2, 2)),
                layers.Flatten(),
                layers.BatchNormalization(),
                layers.Dense(64, activation="relu"),
                layers.Dense(labels),
            ]
        )
        self.model.compile(
            optimizer="adam", loss=losses.SparseCategoricalCrossentropy(from_logits=True), metrics=["accuracy"]
        )
        self.model.summary()

    def set_labels_map(self, labels_map: list[str]) -> None:
        """Sets labels map

        Args:
            labels_map (list[str]): ["ж", ...]
        """
        self.labels_map = labels_map

    def save(
        self,
        dir_path: str = SAVE_DIR_DEFAULT,
    ) -> None:
        """Saves labels map and model using model.save
        NOTE: Call set_labels_map() before!

        Args:
            dir_path (str, optional): directory where to save files. Defaults to SAVE_DIR_DEFAULT
        """
        if not os.path.exists(dir_path):
            logging.info(f"Creating {dir_path} directory")
            os.makedirs(dir_path)

        # Save labels map
        labels_map_path = os.path.join(dir_path, "labels_map.json")
        logging.info(f"Saving labels map to {labels_map_path}")
        with open(labels_map_path, "w+", encoding="utf-8") as labels_map_io:
            json.dump(self.labels_map, labels_map_io, ensure_ascii=False, indent=4)

        # Save model
        model_path = os.path.join(dir_path, "model.keras")
        logging.info(f"Saving model to {model_path}")
        self.model.save(model_path)

    def train(self, images: NDArray[np.float32], labels: NDArray[np.int16], epochs: int = 20):
        """Wrapper for model.fit

        Args:
            images (NDArray[np.uint8]): array (list) of 2D images in 0-1 range of (N, INPUT_HEIGHT, INPUT_WIDTH) shape
            labels (NDArray[np.int16]): labels as integers of (N,) shape
            epochs (int, optional): number of training epochs. Defaults to 20
        """
        logging.info(f"Reshaping training images from shape {images.shape}")
        images = images.reshape(images.shape[0], INPUT_HEIGHT, INPUT_WIDTH, 1)
        logging.info(f"Reshaped into {images.shape}")

        self.model.fit(images, labels, epochs=epochs)

    def predict(self, images: list[MatLike]) -> list[str]:
        """Wrapper for np.argmax(model.predict())

        Args:
            images (list[MatLike]): list of 2D images of size INPUT_WIDTHxINPUT_HEIGHT in 0-255 range to predict

        Returns:
            list[str]: characters per image using labels_map
        """
        np_images = np.asarray(np.asarray(images, dtype=np.float32) / 255.0, dtype=np.float32)
        np_images = np_images.reshape(np_images.shape[0], INPUT_HEIGHT, INPUT_WIDTH, 1)
        predictions = self.model.predict(np_images)
        characters = []
        for prediction in predictions:
            characters.append(self.labels_map[np.argmax(prediction)])
        return characters
