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

    this.websocketPacketId = 1
    this.deviceUpdateSubscription = null

    this.state = {
      chartData:  {
        labels: [],
        datasets: [
        {
            label: "Melbank",
            lineTension: 0.1,
            backgroundColor: "rgba(0,0,0,0.1)",
            borderColor: "rgba(0,0,0,1)",
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
                  maxTicksLimit: 7,
                  callback: function(value, index, values) {
                    return value + ' Hz';
                  }
              }
          }],
          yAxes: [{
              ticks: {
                  min: 0,
                  max: 2.0,
                  stepSize: 0.5
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
    var messageData = JSON.parse(e.data);
    chartData.labels = messageData.frequencies
    chartData.datasets[0].data = messageData.melbank

    // Adjust the axes based on the max
    var melbankMax = Math.max.apply(Math, messageData.melbank);
    var chartOptions = this.state.chartOptions;
    chartOptions.scales.yAxes[0].ticks.min = 0
    chartOptions.scales.yAxes[0].ticks.max = Math.max(chartOptions.scales.yAxes[0].ticks.max, melbankMax)
    chartOptions.scales.yAxes[0].ticks.stepSize = chartOptions.scales.yAxes[0].ticks.max / 4

    this.setState(...this.state, {chartData: chartData, chartOptions: chartOptions})
  }

  handleOpen = e => {
    this.enablePixelVisualization();
  }

  handleClose = e => {
  }

  enablePixelVisualization = () => {
    this.state.ws.json({
      id: this.websocketPacketId,
      type: 'subscribe_event',
      event_type: 'graph_update',
      event_filter: { 'graph_id': this.props.graphId }
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
      this.state.ws.close(1000);
      this.setState(...this.state, {ws: undefined});
    }
  }

  componentDidMount() {
    this.connectWebsocket()
  }

  componentWillUnmount() {
    this.disconnectWebsocket();
  }

  render() {
    const { classes } = this.props;
    
    return (
      <Card variant="outlined">
        <CardContent className={classes.content}>
          <Line data={this.state.chartData} options={this.state.chartOptions}/>
        </CardContent>
      </Card>
    );
  }
}

PixelColorGraph.propTypes = {
  classes: PropTypes.object.isRequired,
  graphId: PropTypes.string.isRequired
};

export default withStyles(styles)(PixelColorGraph);