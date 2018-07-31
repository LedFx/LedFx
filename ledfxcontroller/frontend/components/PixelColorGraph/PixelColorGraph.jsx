import React from "react";
import PropTypes from "prop-types";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import withStyles from "@material-ui/core/styles/withStyles";
import Line from 'react-chartjs-2';
import Sockette from 'sockette';

const styles = theme => ({
  content: {
    minWidth: 120,
    maxWidth: '100%'
  }
});

class PixelColorGraph extends React.Component {

  constructor(props) {
    super(props)

    this.state = {
      pixelIntervalId: undefined,
      chartData:  {
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
      chartOptions: {
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
    }
  }

  handleMessage = e => {
    var chartData = this.state.chartData;
    var messageData = JSON.parse(e.data)
    chartData.labels = messageData.rgb_x
    chartData.datasets[0].data = messageData.r
    chartData.datasets[1].data = messageData.g
    chartData.datasets[2].data = messageData.b
    this.setState(...this.state, {chartData: chartData})
  }

  handleOpen = e => {
    this.enablePixelVisualization();
  }

  handleClose = e => {
    this.disablePixelVisualization();
  }

  enablePixelVisualization = () => {
    var intervalId = setInterval(function() {
      this.state.ws.json({id: 0, type: 'get_pixels', device_id: this.props.deviceId});
    }.bind(this), 100)

    this.setState(...this.state, {pixelIntervalId: intervalId})
  }

  disablePixelVisualization = () => {
    if (this.state.pixelIntervalId != undefined)
    {
      clearInterval(this.state.pixelIntervalId)
      this.setState(...this.state, {pixelIntervalId: undefined})
    }
  }

  connectWebsocket = () => {
    const websocketUrl = 'ws://' + window.location.host + '/api/websocket';
    const ws = new Sockette(websocketUrl, {
      timeout: 5e3,
      maxAttempts: 10,
      onopen: this.handleOpen,
      onmessage: this.handleMessage,
      onclose: this.handleClose,
      onerror: e => console.log('WebSocket Error:', e)
    });

    this.setState(...this.state, {ws: ws});
  }

  disconnectWebsocket = () => {
    if (this.state.ws != undefined) {
      ws.close();
      this.setState(...this.state, {ws: undefined});
    }
  }

  componentDidMount() {
    this.connectWebsocket()
  }

  componentWillUnmount() {
    this.disconnectWebsocket()
  }

  render() {
    const { classes, deviceId } = this.props;
    
    return (
      <Card>
        <CardContent className={classes.content}>
          <Line data={this.state.chartData} options={this.state.chartOptions}/>
        </CardContent>
      </Card>
    );
  }
}

PixelColorGraph.propTypes = {
  classes: PropTypes.object.isRequired,
  deviceId: PropTypes.string.isRequired
};

export default withStyles(styles)(PixelColorGraph);