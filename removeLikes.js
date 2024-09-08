/**
 * This is free and unencumbered software released into the public domain.
 *
 * Anyone is free to copy, modify, publish, use, compile, sell, or
 * distribute this software, either in source code form or as a compiled
 * binary, for any purpose, commercial or non-commercial, and by any
 * means.
 *
 * In jurisdictions that recognize copyright laws, the author or authors
 * of this software dedicate any and all copyright interest in the
 * software to the public domain. We make this dedication for the benefit
 * of the public at large and to the detriment of our heirs and
 * successors. We intend this dedication to be an overt act of
 * relinquishment in perpetuity of all present and future rights to this
 * software under copyright law.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 * IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
 * OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
 * ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
 * OTHER DEALINGS IN THE SOFTWARE.
 *
 * For more information, please refer to <https://unlicense.org>
 */

// --- README README README README README README README README README README README README README --- //
//                                                                                                    //
//   Start vk-new-captcha-solver server, Open <https://vk.com/feed?section=likes> in your browser,    //
//    open developer console (F12 -> Console) and paste this ENTIRE text into it and press Enter.     //
//               It'll ask you for confirmation and then it'll start removing likes.                  //
//                         Type stop() and press Enter to stop the script                             //
//                                                                                                    //
// -------------------------------------------------------------------------------------------------- //

const DELAY_BETWEEN_CLICKS = 700;
const DELAY_BEFORE_CAPTCHA = 4000;
const DELAY_AFTER_CAPTCHA = 4000;
const SOLVER_SERVER = "http://localhost:8090";

const MAX_SCROLL_ATTEMPTS = 10;

let stop_ = false;
let scrollCounter = 0;

/**
 * CALL stop() TO STOP REMOVING LIKES
 */
function stop() {
    console.log("Stopping...");
    stop_ = true;
}

function solveCaptcha(likeBtn) {
    if (stop_) {
        alert("Stopped");
        return;
    }

    console.log("Trying to solve captcha");

    // Get actual image from <img> as base64 without accessing src attribute (because it contains different image)
    const captchaImg = document.querySelector(".box_layout").querySelector("img");
    const canvas = document.createElement("canvas");
    canvas.width = captchaImg.naturalWidth;
    canvas.height = captchaImg.naturalHeight;
    canvas.getContext("2d").drawImage(captchaImg, 0, 0);
    const captchaBase64 = canvas.toDataURL("image/png");

    const request = new XMLHttpRequest();
    request.onreadystatechange = function () {
        if (this.readyState != 4) return;

        // Default result will be "-" to get a new captcha in case of solving error
        let result = "-";
        if (this.status == 200) result = this.responseText;
        console.log("Solved: " + result);

        // Fill result
        const form = document.querySelector(".box_layout").querySelector("form");
        const formInput = form.querySelector("input");
        formInput.focus();
        document.execCommand("insertText", false, result);

        // Submit
        const formBtn = form.querySelector("button");
        setTimeout(function () {
            formBtn.click();
        }, 100);

        // Continue main process
        setTimeout(function () {
            removeLike(likeBtn, true);
        }, 1000);
    };

    // Send request to solver
    request.open("POST", SOLVER_SERVER, true);
    request.setRequestHeader("Content-Type", "text/plain");
    request.send(captchaBase64);
}

function removeLike(likeBtn, afterCaptcha) {
    if (stop_) {
        alert("Stopped");
        return;
    }

    // Look for captcha and wait for user to solve it
    if (document.getElementsByClassName("box_layout").length !== 0) {
        if (!afterCaptcha) console.log("Found box_layout! Waiting " + DELAY_BEFORE_CAPTCHA + "ms before solving it");
        setTimeout(function () {
            solveCaptcha(likeBtn);
        }, DELAY_BEFORE_CAPTCHA);
        return;
    }

    // Repeat only after delay
    if (afterCaptcha) {
        console.log("Captcha removed! Waiting " + DELAY_AFTER_CAPTCHA + "ms");
        setTimeout(function () {
            findAndRemoveLike(false);
        }, DELAY_AFTER_CAPTCHA);
        return;
    }

    // Remove like
    likeBtn.scrollIntoViewIfNeeded(true);
    likeBtn.click();
    console.log("Clicked on " + likeBtn);

    // Rinse and repeat
    findAndRemoveLike(false);
}

function findAndRemoveLike(afterCaptcha) {
    if (stop_) {
        alert("Stopped");
        return;
    }

    // Search for like containers
    const likeBtns = document.getElementsByClassName("like_btns");
    if (likeBtns.length === 0) {
        if (scrollCounter >= MAX_SCROLL_ATTEMPTS) {
            alert("All likes removed!\nPlease refresh page and run script again to make sure everything is removed");
            return;
        }

        console.log("No more like buttons found! Trying to scroll down");
        window.scrollTo(0, document.body.scrollHeight);
        scrollCounter++;
        setTimeout(function () {
            findAndRemoveLike(false);
        }, 1000);
        return;
    }

    // Try to find first active like
    let likeBtnTemp = null;
    for (const element of likeBtns) {
        const likeBtnPri = element.children[0];
        const likeBtnSec = likeBtnPri.children[0];
        if (likeBtnPri.className.includes("active")) likeBtnTemp = likeBtnPri;
        else if (likeBtnSec.className.includes("active")) likeBtnTemp = likeBtnSec;
        else continue;
        break;
    }

    // Exit if no more active likes
    if (likeBtnTemp === null) {
        if (scrollCounter >= MAX_SCROLL_ATTEMPTS) {
            alert("All likes removed!\nPlease refresh page and run script again to make sure everything is removed");
            return;
        }

        console.log("No more active like buttons found! Trying to scroll down");
        likeBtns[likeBtns.length - 1].scrollIntoView(true);
        scrollCounter++;
        setTimeout(function () {
            findAndRemoveLike(false);
        }, 1000);
        return;
    }

    // Found new likes, reset counter
    scrollCounter = 0;

    // We need to click on this shit
    const likeBtn = likeBtnTemp;

    // Normal mode
    if (!afterCaptcha) {
        console.log("Trying to remove like after " + DELAY_BETWEEN_CLICKS + "ms");
        setTimeout(function () {
            removeLike(likeBtn, false);
        }, DELAY_BETWEEN_CLICKS);
    }

    // Repeat captcha checks
    else {
        removeLike(likeBtn, true);
    }
}

// Start recursion
if (confirm("Do you really want to start removing likes?\nYou can type stop() at any time to stop"))
    findAndRemoveLike(false);
