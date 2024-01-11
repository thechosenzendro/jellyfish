const syncSocket = new WebSocket("ws://localhost:8000/sync")

syncSocket.onopen = (event) => {
    console.log("Connected to the sync socket")
    document.dispatchEvent(new Event("syncConnected"))
}

syncSocket.onclose = (event) => {
    console.error("Disconnected from the sync socket")
}

syncSocket.on = (action, cb) => {
    const old_onmessage = syncSocket.onmessage
    console.log(old_onmessage)
    syncSocket.onmessage = async (event) => {
        const data = JSON.parse(event.data)
        console.log(`Got some data! Is this right?: ${event.data}`)
        if (data.action == action) {
            await cb(data)
        }
        else {
            old_onmessage(data)
        }
    }
}

syncSocket.get = (request) => {
    syncSocket.send(JSON.stringify(request))
    return new Promise((resolve, reject) => {

        syncSocket.onerror = (err) => {
            console.log(`An error happened during the GET operation: ${err}`)
            reject(err)
        }
        syncSocket.onmessage = (event) => {
            console.log(`Got data!: ${event.data}`)
            resolve(event.data)
        }
    })
}

document.addEventListener("healthcheck", async () => {
    function markAsPassed(elementId) {
        const element = document.getElementById(elementId)
        element.setAttribute("class", "green_text")
        element.innerHTML = "OK"
    }

    function markAsFailed(elementId, message) {
        const element = document.getElementById(elementId)
        element.setAttribute("class", "alert_text")
        element.innerHTML = `Error: ${message}`
    }


    console.log("Healthcheck!")
    const icon = document.getElementById("healthcheck_icon")
    try {
        const healthcheck_result = await (await fetch("/healthcheck")).json()
        markAsPassed("server_check")
        if (healthcheck_result.trade_node_check == true) {
            markAsPassed("trade_node_check")
            icon.setAttribute("fill", "#008000")
        }
        else {
            markAsFailed("trade_node_check", "Server se nemůže připojit k obchodním uzlům.")
            icon.setAttribute("fill", " #FF0000")
        }

        if (healthcheck_result.broker_api_check == true) {
            markAsPassed("broker_api_check")
            icon.setAttribute("fill", "#008000")
        }
        else {
            markAsFailed("broker_api_check", "Server se nemůže připojit k API brokera.")
            icon.setAttribute("fill", " #FF0000")
        }

    } catch {
        markAsFailed("server_check", "Nelze se připojit k serveru.")
        markAsFailed("trade_node_check", "Nelze ověřit kvůli předchozí chybě.")
        markAsFailed("broker_api_check", "Nelze ověřit kvůli předchozí chybě.")
        icon.setAttribute("fill", " #FF0000")
    }

})
document.addEventListener("onbeforeunload", () => {
    document.removeEventListener("healthcheck")
    document.removeEventListener("onbeforeunload")
})
setInterval(() => { document.dispatchEvent(new Event("healthcheck")) }, 1000)

async function toggleGeneral(btn) {
    const label = btn.getElementsByClassName("center")[0]
    console.log(label)
    if (label.innerHTML == "STOP") {
        if (confirm("Opravdu chcete zastavit obchodování?")) {
            const result = JSON.parse(await syncSocket.get({ action: "stop_trading" }))
            if (result.result == "ok") {
                btn.setAttribute("class", "green btn center")
                label.innerHTML = "START"
            }
            else {
                alert(`Error: ${result}`)
            }
            console.log(result)

        }
    }
    else {
        const result = JSON.parse(await syncSocket.get({ action: "start_trading" }))
        if (result.result == "ok") {
            btn.setAttribute("class", "alert btn center")
            label.innerHTML = "STOP"
        }
        else {
            alert(`Error: ${result}`)
        }
        console.log(result)


    }
}