const startButton = document.getElementById("start-btn");
const sendButton = document.getElementById("send-btn");
const refNumberWrapper = document.getElementById("ref-number-wrapper");
const refNumberElem = document.getElementById("ref-number");
const moreInfoElem = document.getElementById("more-info-link");
const serverURL = "http://localhost:5000";

let transactionId = null;
let webview = null;

startButton.addEventListener("click", e => {
    e.preventDefault();
    startButton.disabled = true;
    refNumberWrapper.style.visibility = "hidden";
    moreInfoElem.style.visibility = "hidden";
    startButton.innerText = "Loading...";
    fetch(serverURL + "/url").then(r => r.json()).then(body => {
        startButton.innerText = "In Progress...";
        transactionId = body["txid"];
        /*
        * The opener of MoneyGram's UI may use a popup, mobile webview, or browser tab.
         */
        webview = window.open(body["url"], "webview", "width=500,height=800");
        /*
        * This is the key piece of client-side code. MoneyGram will make a postMessage request
        * to the opener of the MoneyGram UI, signaling to the opener that the flow is complete
        * and that the opener may close the MoneyGram UI.
        *
        * The body of the message is the same SEP-24 transaction object included in the response
        * to `GET /transaction?id=`.
        *
        * https://developer.mozilla.org/en-US/docs/Web/API/Window/postMessage
        * https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0024.md#transaction-history
        *
         */
        window.addEventListener("message", addSendButton);
    });
});

function addSendButton(_e) {
    sendButton.disabled = false;
    webview.close();
}

sendButton.addEventListener("click", _e => {
    sendButton.innerText = "Sending..."
    sendButton.disabled = true;
    fetch(
        serverURL + "/send",
        {
            method: "POST",
            body: JSON.stringify({
                "id": transactionId
            }),
            headers: {
                "Content-Type": "application/json"
            }
        }
    ).then(r => r.json()).then(body => {
        refNumberElem.textContent = body["refNumber"];
        moreInfoElem.href = body["url"];
        moreInfoElem.style.visibility = "visible"
        refNumberWrapper.style.visibility = "visible";
        sendButton.innerText = "Send";
        startButton.innerText = "Restart";
        startButton.disabled = false;
    });
});