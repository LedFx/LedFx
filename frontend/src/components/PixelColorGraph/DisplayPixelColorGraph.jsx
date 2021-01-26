import React from 'react';
import PropTypes from 'prop-types';
import withStyles from '@material-ui/core/styles/withStyles';
import { Line } from 'react-chartjs-2';
import { createWebSocket } from 'utils/api/websocket';
import Box from '@material-ui/core/Box';

const styles = theme => ({
    content: {
        minWidth: 120,
        maxWidth: '100%',
        height: 200,
    },
});

class DisplayPixelColorGraph extends React.Component {
    constructor(props) {
        super(props);

        this.ws = undefined;
        this.websocketActive = false;
        this.websocketPacketId = 1;
        this.displayUpdateSubscription = null;
        this.state = this.getChartOptionsForDisplay(props.display);
    }

    getChartOptionsForDisplay(display) {
        console.log('AND AGAAAAIN: Hole 99999 display.config.pixel_count missing...', display);
        const { pixel_count } = display.config[display.id];
        // const { pixel_count } = { pixel_count: 50 };

        return {
            chartData: {
                labels: Array.apply(null, { length: pixel_count }).map(Function.call, Number),
                datasets: [
                    {
                        label: 'Red',
                        lineTension: 0.1,
                        backgroundColor: 'rgba(255,0,0,0.3)',
                        borderColor: 'rgba(255,0,0,1)',
                        pointRadius: 0,
                        data: new Array(pixel_count).fill(0),
                    },
                    {
                        label: 'Green',
                        lineTension: 0.1,
                        backgroundColor: 'rgba(0,255,0,0.3)',
                        borderColor: 'rgba(0,255,0,1)',
                        pointRadius: 0,
                        data: new Array(pixel_count).fill(0),
                    },
                    {
                        label: 'Blue',
                        lineTension: 0.1,
                        backgroundColor: 'rgba(0,0,255,0.3)',
                        borderColor: 'rgba(0,0,255,1)',
                        pointRadius: 0,
                        data: new Array(pixel_count).fill(0),
                    },
                ],
            },
            chartOptions: {
                responsive: true,
                maintainAspectRatio: false,
                tooltips: { enabled: false },
                hover: { mode: null, animationDuration: 0 },
                animation: {
                    duration: 0,
                },
                responsiveAnimationDuration: 0,
                scales: {
                    xAxes: [
                        {
                            gridLines: {
                                display: false,
                            },
                            ticks: {
                                max: pixel_count,
                                min: 0,
                                maxTicksLimit: 7,
                            },
                        },
                    ],
                    yAxes: [
                        {
                            // stacked: true,
                            ticks: {
                                display: false,
                                min: 0,
                                max: 256,
                                stepSize: 64,
                            },
                            gridLines: {
                                display: false,
                                color: 'rgba(0, 0, 0, .125)',
                            },
                        },
                    ],
                },
                legend: {
                    display: false,
                },
            },
        };
    }

    handleMessage = e => {
        var messageData = JSON.parse(e.data);

        // Ensure this message is for the current display. This can happen
        // during transistions between displays where the component stays
        // loaded
        if (messageData.display_id !== this.props.display.id) {
            return;
        }

        this.setState(({ chartData, chartData: { datasets } }) => ({
            chartData: {
                ...chartData,
                datasets: [
                    { ...datasets[0], data: messageData.pixels[0] },
                    { ...datasets[1], data: messageData.pixels[1] },
                    { ...datasets[2], data: messageData.pixels[2] },
                ],
            },
        }));
    };

    handleOpen = e => {
        this.enablePixelVisualization(this.props.display);
        this.websocketActive = true;
    };

    handleClose = e => {
        this.websocketActive = false;
    };

    enablePixelVisualization = display => {
        if (this.ws) {
            this.ws.json({
                id: this.websocketPacketId,
                type: 'subscribe_event',
                event_type: 'display_update',
                event_filter: { display_id: display.id },
            });
            this.displayUpdateSubscription = this.websocketPacketId;
            this.websocketPacketId++;
        }
    };

    disablePixelVisualization = () => {
        this.ws.json({
            id: this.websocketPacketId,
            type: 'unsubscribe_event',
            subscription_id: this.displayUpdateSubscription,
        });
        this.displayUpdateSubscription = null;
        this.websocketPacketId++;
    };

    connectWebsocket = () => {
        this.ws = createWebSocket({
            timeout: 5e3,
            maxAttempts: 10,
            onopen: this.handleOpen,
            onmessage: this.handleMessage,
            onclose: this.handleClose,
            onerror: e => console.log('WebSocket Error:', e),
        });
    };

    disconnectWebsocket = () => {
        if (this.ws !== undefined && this.websocketActive) {
            this.ws.close(1000);
            this.ws = undefined;
        }
    };

    componentDidMount() {
        this.connectWebsocket();
    }

    componentWillUnmount() {
        this.disconnectWebsocket();
    }

    componentDidUpdate(prevProps) {
        const { display } = this.props;
        if (prevProps.display.id !== display.id && this.websocketActive) {
            this.disablePixelVisualization();
            this.enablePixelVisualization(display);
            this.setState(this.getChartOptionsForDisplay(display));
        }
    }

    render() {
        const { classes } = this.props;
        console.log(this.props);
        return (
            <Box className={classes.content}>
                <Line data={this.state.chartData} options={this.state.chartOptions} />
            </Box>
        );
    }
}

DisplayPixelColorGraph.propTypes = {
    classes: PropTypes.object.isRequired,
    display: PropTypes.object.isRequired,
};

export default withStyles(styles)(DisplayPixelColorGraph);
