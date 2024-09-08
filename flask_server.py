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

For more information, please refer tuo <https://unlicense.org>
"""

import base64
import gc
import logging
import os

import cv2
import numpy as np
from flask import Flask, Response, request
from keras import Sequential

from _version import __version__
from extract_characters import extract_characters
from model import INPUT_HEIGHT, INPUT_WIDTH

SERVER_IP_PORT_DEFAULT = "127.0.0.1:8090"


class FlaskServer:
    def __init__(
        self,
        model: Sequential,
        save_results: str | None = None,
        segmentation_debug: bool = False,
        segmentation_params: dict[str, int] | None = None,
    ) -> None:
        """Initializes FlaskServer instance

        Args:
            model (Sequential): recognition model
            save_results (str | None = None): directory to save solved captchas (directory must exists)
            segmentation_debug (bool, optional): for extract_characters()
            segmentation_params (dict[str, int] | None, optional): for extract_characters()
        """
        self._model = model
        self._save_results = save_results
        self._segmentation_debug = segmentation_debug
        self._segmentation_params = segmentation_params

        self.app = Flask(__name__)

        @self.app.route("/", methods=["POST"])
        def _solve() -> Response:  # pyright: ignore[reportUnusedFunction]
            """Send POST request to / with image as base64 (text/plain body) to solve captcha

            Returns:
                Response: result, 200 or any other code in case of error
            """
            data = request.get_data(as_text=True)
            if not data:
                logging.warning(f"Empty request from {request.remote_addr}")
                return Response(status=400)

            logging.info(f"Request from {request.remote_addr}")
            try:
                # Decode from URI and base64
                if "," in data:
                    data = data.split(",")[1]
                image_bytes = np.fromstring(base64.b64decode(data), np.uint8)
                image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)

                # Apply segmentation
                segments = extract_characters(
                    image,
                    output_width=INPUT_WIDTH,
                    output_height=INPUT_HEIGHT,
                    debug=self._segmentation_debug,
                    params=self._segmentation_params,
                )
                # Predict and return
                output = "".join(self._model.predict(segments))
                logging.info(f"Solved: {output}")
                if self._save_results:
                    logging.info(f'Saving as {os.path.join(self._save_results, f"{output}.png")}')
                    with open(os.path.join(self._save_results, f"{output}.png"), "wb+") as file_io:
                        file_io.write(cv2.imencode(".png", image)[1].tobytes())

                response = Response(output, status=200)

            except Exception as e:
                logging.error(f"Error solving captcha: {e}", e)
                response = Response(str(e), status=500)

            response.mimetype = "text/plain"
            response.headers.add("Access-Control-Allow-Origin", "*")

            gc.collect()

            return response

    def run(self, ip: str, port: int) -> None:
        """Starts server (blocking)

        Args:
            ip (str): server's host
            port (int): server's port
        """
        logging.info(f"Starting server on {ip}:{port}")
        self.app.run(ip, port)
