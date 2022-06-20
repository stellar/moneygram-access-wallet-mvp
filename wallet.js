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
        webview = window.open(body["url"], "webview", "width=500,height=800");
        window.addEventListener("message", addSendButton);
    });
});

function addSendButton(_e) {
    sendButton.disabled = false;
    console.log(webview);
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