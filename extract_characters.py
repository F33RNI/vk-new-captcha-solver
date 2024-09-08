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

import logging

import cv2
import numpy as np
from cv2.typing import MatLike

PARAMS_DEFAULT: dict[str, int] = {
    "no_background_mask_blur_kernel_x": 3,
    "no_background_mask_blur_kernel_y": 3,
    "no_background_mask_threshold": 180,
    "no_background_mask_erode_kernel_x": 3,
    "no_background_mask_erode_kernel_y": 2,
    "floodfill_threshold": 39,
    "group_threshold": 2,
    "min_character_width": 34,
    "max_character_width": 110,
    "min_character_height": 34,
    "max_character_height": 110,
    "min_pixel_density": 12,
    "rects_group_threshold": 2,
    "rects_group_eps": 45,
}


def extract_characters(
    image: MatLike,
    output_width: int | None = None,
    output_height: int | None = None,
    debug: bool = False,
    params: dict[str, int] | None = None,
) -> list[MatLike]:
    """Segments captcha into characters

    BGR Image -> Gray -> Blur gray -> Threshold -> Erode ----- |
        |                                                 BRG Masked -> Floodfill -> Filter -> Group rects -> Cut
        ---------------------------->------------------------- |

    Args:
        image (MatLike): input image in BGR format
        output_width (int | None, optional): set to scale output image. Must be < image width. Defaults to None
        output_height (int | None, optional): set to scale output image. Must be < image height. Defaults to None
        debug (bool, optional): set to True to show debug image processing before returning result. Defaults to False
        params (dict[str, int] | None, optional): segmentation parameters. Defaults to PARAMS_DEFAULT

    Raises:
        Exception: in case of wrong output_width, output_height or any other error

    Returns:
        list[MatLike]: list of extracted characters as 2D arrays where each pixel in 0-255 range with black background
    """
    # Fix given parameters
    if params is None:
        params = PARAMS_DEFAULT
    else:
        for param_key, param_default_val in PARAMS_DEFAULT.items():
            if param_key not in params:
                params[param_key] = param_default_val

    image_w = image.shape[1]
    image_h = image.shape[0]

    # Check output size
    if output_width is not None and output_width > image_w:
        raise Exception("output_width must be less or equal to the image width")
    if output_height is not None and output_height > image_h:
        raise Exception("output_height must be less or equal to the image height")

    logging.info(f"Segmenting image {image_w}x{image_h}")

    # Initialize debug image and draw initial image on it
    debug_view = None
    if debug:
        debug_view = np.zeros((image_h * 6, image_w * 3, 3), dtype=np.uint8)
        debug_view = cv2.putText(
            debug_view,
            "Press any key",
            (20, image_h * 5 + (image_h // 2 - 10)),
            cv2.FONT_HERSHEY_DUPLEX,
            1,
            (255, 255, 255),
            1,
        )
        debug_view = cv2.putText(
            debug_view,
            "to continue",
            (20, image_h * 5 + (image_h // 2 + 20)),
            cv2.FONT_HERSHEY_DUPLEX,
            1,
            (255, 255, 255),
            1,
        )
        debug_view = cv2.rectangle(debug_view, (0, image_h * 5), (image_w - 1, image_h * 6 - 1), (255, 255, 255), 1)
        debug_view[:image_h, :image_w] = image

    # Calculate mask that removes background (leaves only characters and lines)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_kernel = (params["no_background_mask_blur_kernel_x"], params["no_background_mask_blur_kernel_y"])
    gray_blurred = cv2.blur(gray, blur_kernel)
    _, no_background_mask = cv2.threshold(
        gray_blurred, params["no_background_mask_threshold"], 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )
    kernel = (params["no_background_mask_erode_kernel_x"], params["no_background_mask_erode_kernel_y"])
    no_background_mask = cv2.erode(no_background_mask, kernel, iterations=1)

    # Remove background
    mask_bgr = cv2.cvtColor(no_background_mask, cv2.COLOR_GRAY2BGR)
    image_masked = cv2.bitwise_and(image, mask_bgr)

    # Draw background removal
    if debug:
        debug_view[image_h : image_h * 2, :image_w] = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        debug_view[image_h * 2 : image_h * 3, :image_w] = cv2.cvtColor(gray_blurred, cv2.COLOR_GRAY2BGR)
        debug_view[image_h * 3 : image_h * 4, :image_w] = cv2.cvtColor(no_background_mask, cv2.COLOR_GRAY2BGR)
        debug_view[image_h * 4 : image_h * 5, :image_w] = image_masked

    # Convert floodfill threshold to the BGR scalar
    color_threshold = (params["floodfill_threshold"], params["floodfill_threshold"], params["floodfill_threshold"])

    rects = []
    characters_mask = np.zeros((image_h, image_w), dtype=np.uint8)
    debug_ctr = 0

    # Sweep across middle Y
    for x in range(0, image_w):
        if not no_background_mask[image_h // 2, x]:
            continue

        # Floodfill by color
        mask_temp = np.zeros((image_h + 2, image_w + 2), dtype=np.uint8)
        _, debug_result, floodfill_mask, rect = cv2.floodFill(
            image_masked.copy(),
            mask_temp,
            (x, image_h // 2),
            (255, 255, 255),
            color_threshold,
            color_threshold,
            cv2.FLOODFILL_FIXED_RANGE,
        )

        # Apply background removal
        character_mask = cv2.bitwise_and(floodfill_mask[:-2, :-2] * 255, no_background_mask)

        # Filter by size
        rect_x, rect_y, rect_w, rect_h = rect
        if (
            rect_w >= params["min_character_width"]
            and rect_w <= params["max_character_width"]
            and rect_h >= params["min_character_height"]
            and rect_h <= params["max_character_height"]
        ):
            # Calculate number of pixels and ignore empty ones
            pixels = cv2.countNonZero(character_mask[rect_y : rect_y + rect_h, rect_x : rect_x + rect_w])
            if pixels == 0:
                continue

            # Calculate density and filter by it
            density = pixels / (rect_w * rect_h) * 100
            if density < params["min_pixel_density"]:
                continue

            # Draw 6 dots with interval between for debug
            if debug and x % (image_w // 20) == 0 and debug_ctr < 6:
                debug_result = cv2.line(debug_result, (0, image_h // 2), (image_w, image_h // 2), (255, 0, 255), 1)
                debug_result = cv2.circle(debug_result, (x, image_h // 2), 3, (0, 200, 0), -1)
                debug_result = cv2.putText(
                    debug_result, f"Test sample @ X={x}", (5, 15), cv2.FONT_HERSHEY_PLAIN, 1, (0, 200, 0), 1
                )
                debug_view[image_h * debug_ctr : image_h * (debug_ctr + 1), image_w : image_w * 2] = debug_result
                debug_ctr += 1

            # Merge characters
            characters_mask = cv2.bitwise_or(character_mask, characters_mask)
            rects.append(rect)

    # Check for any bounding rects
    if not rects:
        return []

    # Remove overlaying rects
    rects_grouped, _ = cv2.groupRectangles(
        rects, params["rects_group_threshold"], eps=params["rects_group_eps"] / 100.0
    )

    # Fix empty pixels
    characters_mask = cv2.dilate(characters_mask, (3, 3), iterations=1)
    characters_mask = cv2.erode(characters_mask, (3, 3), iterations=1)

    # Highlight segmented characters
    if debug:
        characters_mask_debug = cv2.cvtColor(characters_mask, cv2.COLOR_GRAY2BGR)
        for rect in rects_grouped:
            x, y, w, h = rect
            cv2.rectangle(characters_mask_debug, (x, y), (x + w, y + h), (255, 0, 255), 1)
        characters_mask_debug = cv2.putText(
            characters_mask_debug,
            f"Found: {len(rects_grouped)} chars",
            (5, 15),
            cv2.FONT_HERSHEY_PLAIN,
            1,
            (0, 200, 0),
            1,
        )
        debug_view[:image_h, image_w * 2 : image_w * 3] = characters_mask_debug

    # Finally, extract segmented characters and resize them
    characters = []
    for rect in rects_grouped:
        x, y, w, h = rect
        character = characters_mask[y : y + h, x : x + w]
        if output_width is not None and output_height is not None:
            character = cv2.resize(character, (output_width, output_height), interpolation=cv2.INTER_NEAREST)
        characters.append(character)

    if debug:
        # Draw each characters scaled
        for i, character in enumerate(characters):
            if i > 4:
                break
            debug_view[
                image_h * (i + 1) : image_h * (i + 1) + character.shape[0],
                image_w * 2 : image_w * 2 + character.shape[1],
            ] = cv2.cvtColor(character, cv2.COLOR_GRAY2BGR)
            debug_view = cv2.rectangle(
                debug_view,
                (image_w * 2, image_h * (i + 1)),
                (image_w * 2 + character.shape[1], image_h * (i + 1) + character.shape[0]),
                (255, 0, 255),
                1,
            )

        # Show debug image
        cv2.imshow("Debug", debug_view)
        cv2.waitKey(0)
        cv2.destroyWindow("Debug")

    logging.info(f"Found {len(characters)} characters")
    return characters
