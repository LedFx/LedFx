import React from "react";
import PropTypes from "prop-types";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import withStyles from "@material-ui/core/styles/withStyles";
import { Line } from 'react-chartjs-2';
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

    this.websocketActive = false;
    this.websocketPacketId = 1
    this.deviceUpdateSubscription = null
    this.state = this.getChartOptionsForDevice(props.device)
  }

  getChartOptionsForDevice(device)
  {
    return {
      chartData:  {
        labels: Array.apply(null, {length: device.config.pixel_count}).map(
          Function.call, Number),
        datasets: [
        {
            label: "Red",
            lineTension: 0.1,
            backgroundColor: "rgba(255,0,0,0.1)",
            borderColor: "rgba(255,0,0,1)",
            pointRadius: 0,
            data: new Array(device.config.pixel_count).fill(0),
        },
        {
            label: "Green",
            lineTension: 0.1,
            backgroundColor: "rgba(0,255,0,0.1)",
            borderColor: "rgba(0,255,0,1)",
            pointRadius: 0,
            data: new Array(device.config.pixel_count).fill(0),
        },
        {
            label: "Blue",
            lineTension: 0.1,
            backgroundColor: "rgba(0,0,255,0.1)",
            borderColor: "rgba(0,0,255,1)",
            pointRadius: 0,
            data: new Array(device.config.pixel_count).fill(0),
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
                max: device.config.pixel_count,
                min: 0,
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
    var messageData = JSON.parse(e.data);

    // Ensure this message is for the current device. This can happen
    // during transistions between devices where the component stays
    // loaded
    if (messageData.device_id != this.props.device.id) {
      return;
    }

    var chartData = this.state.chartData
    chartData.datasets[0].data = messageData.pixels[0]
    chartData.datasets[1].data = messageData.pixels[1]
    chartData.datasets[2].data = messageData.pixels[2]
    this.setState(...this.state, {chartData: chartData})
  }

  handleOpen = e => {
    this.enablePixelVisualization(this.props.device);
    this.websocketActive = true
  }

  handleClose = e => {
    this.websocketActive = false
  }

  enablePixelVisualization = (device) => {
    this.state.ws.json({
      id: this.websocketPacketId,
      type: 'subscribe_event',
      event_type: 'device_update',
      event_filter: { 'device_id': device.id }
    })
    this.deviceUpdateSubscription = this.websocketPacketId;
    this.websocketPacketId++;
  }

  disablePixelVisualization = () => {
    this.state.ws.json({
      id: this.websocketPacketId,
      type: 'unsubscribe_event',
      subscription_id: this.deviceUpdateSubscription
    })
    this.deviceUpdateSubscription = null;
    this.websocketPacketId++;
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
      this.state.ws.close();
      this.setState(...this.state, {ws: undefined});
    }
  }

  componentDidMount() {
    this.connectWebsocket()
  }

  componentWillUnmount() {
    this.disconnectWebsocket();
  }

  componentWillReceiveProps(nextProps) {
    if (this.websocketActive) {
      this.disablePixelVisualization()
      this.enablePixelVisualization(nextProps.device)
      this.setState(...this.state, 
        this.getChartOptionsForDevice(nextProps.device))
    }
  }

  render() {
    const { classes, device } = this.props;
    
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
  device: PropTypes.object.isRequired
};

export default withStyles(styles)(PixelColorGraph);