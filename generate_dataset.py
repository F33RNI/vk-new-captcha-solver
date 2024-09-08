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

import gc
import glob
import logging
import os

import cv2
import numpy as np
from cv2.typing import MatLike
from numpy.typing import NDArray

from extract_characters import extract_characters
from model import INPUT_HEIGHT, INPUT_WIDTH


def generate_dataset(
    files_path: str, target_size: int = 0, debug: bool = False, params: dict[str, int] | None = None
) -> tuple[NDArray[np.float32], NDArray[np.int16], list[str], int]:
    """Parses images and build dataset from it

    Args:
        files_path (str): file pattern for glob. Example: "dataset/*.png"
        target_size (int, optional): to which number of samples expand dataset by randomly scaling / rotating images.
        Set to 0 to use as is without expanding
        debug (bool, optional): for extract_characters() function. Defaults to False
        params (dict[str, int] | None, optional): for extract_characters() function. Defaults to None

    Returns:
        tuple[NDArray[np.float32], NDArray[np.int16], list[str], int]: (2D images in 0-1 range (0 is background),
        of shape (N, INPUT_HEIGHT, INPUT_WIDTH), labels as integers of shape (N, ),
        labels map (list of unique labels), number of unique labels)
    """
    files = glob.glob(files_path)
    logging.info(f"Found {len(files)} dataset files")

    images_n = 0

    # Extract raw dataset from files
    dataset: dict[str, list[MatLike]] = {}
    for file in files:
        try:
            # Read image
            stream = open(file, "rb")
            image = cv2.imdecode(np.frombuffer(stream.read(), dtype=np.uint8), cv2.IMREAD_COLOR)
            stream.close()

            # Extract labels from file name
            labels = list(os.path.splitext(os.path.basename(file))[0])

            # Segment image
            characters = extract_characters(
                image, output_width=INPUT_WIDTH, output_height=INPUT_HEIGHT, debug=debug, params=params
            )

            # Check
            if not characters:
                logging.warning(f"Unable to segment {file}! No characters detected")
                continue
            if len(labels) != len(characters):
                logging.warning(
                    f"Unable to segment {file}! Found {len(characters)} characters. Expected: {len(labels)}"
                )
                continue

            # Append to global lists
            for i, label in enumerate(labels):
                if label not in dataset:
                    dataset[label] = [characters[i]]
                else:
                    dataset[label].append(characters[i])
                images_n += 1

        except Exception as e:
            logging.error(f"Unable to parse image {file}: {e}")

    if len(dataset) == 0:
        logging.warning("No images for dataset")
        return np.asarray([]), np.asarray([]), [], 0

    # Sort alphabetically
    sorted_labels = sorted(dataset.keys(), key=lambda lb: lb.lower())
    dataset_sorted: dict[str, list[MatLike]] = {}
    for sorted_label in sorted_labels:
        dataset_sorted[sorted_label] = dataset[sorted_label]

    logging.info(f"Raw dataset contains {images_n} images and {len(dataset_sorted)} unique labels")
    gc.collect()

    if target_size > 0:
        logging.info(f"Expanding dataset up to {target_size} images")
        images_per_label = [len(img) for _, img in dataset_sorted.items()]
        expand_image_idx = [0] * len(dataset_sorted)
        expand_label_idx = 0
        for _ in range(target_size - images_n):
            label = list(dataset_sorted.keys())[expand_label_idx]
            image = dataset_sorted[label][expand_image_idx[expand_label_idx]]

            width = image.shape[1]
            height = image.shape[0]

            # Calculate the rotation matrix
            rotation_range = np.random.randint(-10, 10)
            rotation_matrix = cv2.getRotationMatrix2D((width / 2, height / 2), rotation_range, 1)
            rotation_matrix = np.vstack([rotation_matrix, [0, 0, 1]])

            # Calculate shift, scale and stretch matrix
            shift_range = int(min(width, height) * (np.random.randint(-5, 5) / 100.0))

            stretch_range_x = np.random.randint(-10, 10) / 100.0
            stretch_range_x += 1.0
            stretch_range_y = np.random.randint(-10, 10) / 100.0
            stretch_range_y += 1.0

            stretch_matrix = np.array(
                [[stretch_range_x, 0, shift_range], [0, stretch_range_y, shift_range]], dtype=np.float32
            )

            # Combine them
            combined_matrix = np.matmul(stretch_matrix, rotation_matrix)

            # Apply matrices
            image_new = cv2.warpAffine(image, combined_matrix, (width, height), borderValue=(0, 0, 0))
            del stretch_matrix
            del rotation_matrix
            del combined_matrix

            # Apply threshold
            _, image_new = cv2.threshold(image_new, 180, 255, cv2.THRESH_BINARY)

            # Append generated image
            dataset_sorted[label].append(image_new)

            expand_image_idx[expand_label_idx] += 1
            if expand_image_idx[expand_label_idx] == images_per_label[expand_label_idx]:
                expand_image_idx[expand_label_idx] = 0

            expand_label_idx += 1
            if expand_label_idx == len(dataset_sorted):
                expand_label_idx = 0

    # Convert into 2 lists
    label_idx = []
    images = []
    labels_map = []
    for i, (label, label_images) in enumerate(dataset_sorted.items()):
        labels_map.append(label)
        for image in label_images:
            label_idx.append(i)
            images.append(image / 255.0)

    images = np.asarray(images, dtype=np.float32)
    label_idx = np.asarray(label_idx, dtype=np.int16)
    logging.info(f"images shape: {images.shape}")
    logging.info(f"label_idx shape: {label_idx.shape}")

    gc.collect()
    return (
        images,
        label_idx,
        labels_map,
        len(dataset_sorted),
    )
