function setColor(ctx, data) {
    states = {
        analyzing: "rgb(0,0,255)",
        bought: "rgb(0, 255, 0)",
        shorting: "rgb(255, 0, 0)",
        noop: "rgb(0,0,0,0.2)"
    }

    return states[data[ctx.p0DataIndex].state]
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
        this.ticker = this.getAttribute("ticker")
        this.graph = null
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
        console.log("Syncing graph!")
        const data = (await syncSocket.get({
            action: "graph_sync",
            ticker: this.ticker,
            sync_time: "7d"
        })).data
        this.chart = new Chart("priceGraph", {
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

            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    zoom: {
                        zoom: {
                            wheel: {
                                enabled: true,
                            },
                            pinch: {
                                enabled: true
                            },
                            mode: 'x',
                        }
                    }
                }
            }
        })


        syncSocket.on("update_graph", async (updateData) => {
            if (updateData.ticker == this.ticker) {
                data.push(updateData)
                const dataset = this.chart.data.datasets[0]
                dataset.data.push(updateData.price)
                this.chart.data.labels.push(updateData.timestamp)
                this.chart.update()

            }

        })
    }
}

window.customElements.define("price-graph", Graph)