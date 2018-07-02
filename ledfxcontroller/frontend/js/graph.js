Chart.defaults.global.defaultFontFamily = '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
Chart.defaults.global.defaultFontColor = '#292b2c';

// Create a RGB visualization graph on the given canvas

class RGBVisualizationGraph {
    constructor(canvasId) {
        var ctx = document.getElementById(canvasId);
        this.graph = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                {
                    label: "Red",
                    lineTension: 0.1,
                    backgroundColor: "rgba(255,0,0,0.1)",
                    borderColor: "rgba(255,0,0,1)",
                    pointRadius: 0,
                    data: [],
                },
                {
                    label: "Green",
                    lineTension: 0.1,
                    backgroundColor: "rgba(0,255,0,0.1)",
                    borderColor: "rgba(0,255,0,1)",
                    pointRadius: 0,
                    data: [],
                },
                {
                    label: "Blue",
                    lineTension: 0.1,
                    backgroundColor: "rgba(0,0,255,0.1)",
                    borderColor: "rgba(0,0,255,1)",
                    pointRadius: 0,
                    data: [],
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                tooltips: {enabled: false},
                hover: {mode: null},
                animation: {
                    duration: 0,
                },
                hover: {
                    animationDuration: 0,
                },
                responsiveAnimationDuration: 0,
                scales: {
                xAxes: [{
                    gridLines: {
                        display: false
                    },
                    ticks: {
                        maxTicksLimit: 7
                    }
                }],
                yAxes: [{
                    ticks: {
                        min: 0,
                        max: 256,
                        stepSize: 64
                    },
                    gridLines: {
                        color: "rgba(0, 0, 0, .125)",
                    }
                }],
                },
                legend: {
                    display: false
                }
            }
        });
    }

    update(data) {
        this.graph.data.labels = data.rgb_x
        this.graph.data.datasets[0].data = data.r
        this.graph.data.datasets[1].data = data.g
        this.graph.data.datasets[2].data = data.b
        this.graph.update(0)
    }

    setPixelMax(pixelMax) {
        this.graph.config.options.scales.yAxes[0].ticks.max = pixelMax
    }
}