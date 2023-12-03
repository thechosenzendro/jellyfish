function setColor(ctx, data) {
    states = {
        analyzing: "rgb(0,0,255)",
        bought: "rgb(0, 255, 0)",
        shorting: "rgb(255, 0, 0)",
        noop: "rgb(0,0,0,0.2)"
    }
    return states[data[ctx.p0DataIndex]["state"]]
}
/*
data {
    label: str,
    price: float,
    state: "analyzing" | "bought" | "shorting" | "noop"
}
*/

class Graph extends HTMLElement {
    constructor() {
        super()
    }
    async connectedCallback() {
        this.innerHTML = `
        <div id="graph" class="chart-container border">
            <canvas id="priceGraph"></canvas>
            <style>
                #graph {
                    position: relative;
                    margin: 10px;
                    height: 300px;
                }
            </style>
        `
        const data = await (await fetch("/sync/graph/1h")).json()
        const chart = new Chart("priceGraph", {
            type: "line",
            data: {
                labels: data.map(datapoint => datapoint.timestamp),
                datasets: [{
                    label: "Cena",
                    data: data.map(datapoint => datapoint.price),
                    segment: {
                        borderColor: ctx => setColor(ctx, data)
                    }
                }]
            },
            options: {}
        })

        document.addEventListener("update", async () => {
            const next = await (await fetch("/sync/graph/next")).json()
            const dataset = chart.data.datasets[0]
            dataset.data.push(next.price)
            chart.data.labels.push(next.timestamp)
            chart.update()

        })
    }
}

window.customElements.define("price-graph", Graph)