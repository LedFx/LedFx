import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  // Tooltip,
  Legend
} from 'chart.js'
import styled from 'styled-components'
import { Radar } from 'react-chartjs-2'
import { useTheme } from '@mui/material/styles'

const RadarChartContainer = styled.div`
  width: 450px;
  margin: 0 auto;
  h2 {
    margin-bottom: 40px;
    font-family: Inter;
    font-style: normal;
    font-weight: 900;
    font-size: 22px;
    color: white;
  }
`

const RadarChart = (props: any) => {
  const theme = useTheme()
  const TrackFeatures = props
  ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Legend)
  const data = {
    labels: [
      'Energy',
      'Danceability',
      'Positiveness',
      'Instrumentalness',
      'Loudness'
    ],
    datasets: [
      {
        label: 'Track Features',
        backgroundColor: `${theme.palette.primary.main}30`,
        borderColor: `${theme.palette.primary.main}dd`,
        borderWidth: 1,
        pointBackgroundColor: `${theme.palette.primary.main}`,
        pointBorderWidth: 2,
        data: [
          TrackFeatures?.energy,
          TrackFeatures?.danceability,
          TrackFeatures?.valence,
          TrackFeatures?.instrumentalness,
          ((TrackFeatures?.loudness || 0) * -1) / 13
        ]
      }
    ]
  }

  const chartOptions = {
    aspectRatio: 1.8,
    responsive: true,
    plugins: {
      legend: {
        display: false
      }
    },
    layout: {
      autoPadding: false
    },
    scales: {
      radial: {
        title: {
          color: '#f00'
        },
        ticks: {
          display: false
        },
        grid: {
          color: '#333'
        },
        angleLines: {
          display: true,
          color: '#333'
        }
      }
    },
    tooltips: {
      callbacks: {
        label(tooltipItem: any) {
          return tooltipItem.yLabel
        }
      }
    }
  }
  return (
    <RadarChartContainer>
      <Radar data={data} options={chartOptions} />
    </RadarChartContainer>
  )
}
export default RadarChart
