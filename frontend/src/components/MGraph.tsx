/* eslint-disable prettier/prettier */
import { useEffect, useState } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  LogarithmicScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import {
  Card,
  CardContent,
  CardHeader,
  Slider,
  Switch,
  TextField,
  useTheme,
} from '@mui/material'
import BladeFrame from './SchemaForm/components/BladeFrame'

ChartJS.register(
  CategoryScale,
  LinearScale,
  LogarithmicScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const MGraph = () => {
  const [data, setData] = useState({} as any)
  const theme = useTheme()

  const [scaleType, setScaleType] = useState(false)

  const [animationDuration, setAnimationDuration] = useState<number>(10)
  const handleSliderChange = (event: Event, newValue: number | number[]) => {
    setAnimationDuration(typeof newValue === 'number' ? newValue : newValue[0])
  }
  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setAnimationDuration(
      event.target.value === '' ? 0 : Number(event.target.value)
    )
  }

  const [fillOpacity, setFillOpacity] = useState<number>(0)
  const handleFillOpacitySliderChange = (
    event: Event,
    newValue: number | number[]
  ) => {
    setFillOpacity(typeof newValue === 'number' ? newValue : newValue[0])
  }
  const handleFillOpacityInputChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setFillOpacity(event.target.value === '' ? 0 : Number(event.target.value))
  }

  const [lineTension, setLineTension] = useState<number>(0.5)
  const handleLineTensionSliderChange = (
    event: Event,
    newValue: number | number[]
  ) => {
    setLineTension(typeof newValue === 'number' ? newValue : newValue[0])
  }
  const handleLineTensionInputChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setLineTension(event.target.value === '' ? 0 : Number(event.target.value))
  }

  interface MessageData {
    frequencies: any[]
    melbank: [number[], number[], number[]]
  }

  useEffect(() => {
    const handleWebsockets = (e: any) => {
      const messageData = e.detail as MessageData
      const chartData = {
        labels: messageData.frequencies,
        datasets: [
          {
            label: '',
            id: 1,
            lineTension,
            backgroundColor: `#0dbedc${fillOpacity.toString(16)}`,
            fill: true,
            borderColor: theme.palette.primary.main,
            pointRadius: 0,
            data: messageData.melbank,
          },
        ],
      }

      // Adjust the axes based on the max
      const chartOptions = {
        responsive: true,
        maintainAspectRatio: true,
        tooltips: { enabled: false },
        hover: {
          animationDuration: 0,
          mode: null,
        },
        animation: {
          duration: animationDuration,
        },
        responsiveAnimationDuration: 0,
        scales: {
          xAxis: {
            display: false,
            maxTicksLimit: 3,
          },
          x: {
            display: true,
            title: {
              display: true,
              text: 'Frequency',
            },
            ticks: {
              borderColor: '#fff',
              maxTicksLimit: 12,
              callback(value: any, _index: any, _values: any) {
                return `${value} Hz`
              },
            },
            grid: {
              color: 'rgba(255, 255, 255, 0)',
              // borderColor: 'rgba(255, 255, 255, 0.15)',
            },
            ...(scaleType && { type: 'logarithmic' }),
          },
          yAxis: {
            min: 0,
            max: 2.0
          },
          y: {
            title: {
              display: true,
              text: 'Melbank',
            },
            ticks: {
              display: false,
              maxTicksLimit: 7,
              callback(value: any, _index: any, _values: any) {
                return `${parseFloat(value).toFixed(2)}`
              },
            },
            // grid: {
            //   color: 'rgba(255, 255, 255, 0)',
            //   // borderColor: 'rgba(255, 255, 255, 0.15)',
            // },
          },
        },
        plugins: {
          legend: {
            display: false,
          },
        },
      }
      setData({ chartData, chartOptions })
    }
    document.addEventListener('graph_update', handleWebsockets)
    return () => {
      document.removeEventListener('graph_update', handleWebsockets)
    }
  }, [animationDuration, fillOpacity, scaleType])


  return (
    <div>
      <Card
        style={{
          maxWidth: 720,
          width: '100%',
          margin: '3rem',
          background: '#1c1c1e',
        }}
      >
        <CardHeader title="Melbank Graph Settings" />
        <CardContent>
          <BladeFrame
            title="Animation Duration"
            style={{ paddingLeft: '1.5rem', marginBottom: '1.5rem' }}
          >
            <Slider
              value={
                typeof animationDuration === 'number' ? animationDuration : 0
              }
              onChange={handleSliderChange}
              valueLabelDisplay="auto"
              min={0}
              max={2000}
            />
            <TextField
              InputProps={{
                endAdornment: 'ms',
              }}
              type="number"
              value={
                typeof animationDuration === 'number' ? animationDuration : 0
              }
              onChange={handleInputChange}
              style={{
                marginLeft: '2rem',
                width: '130px',
                backgroundColor: theme.palette.background.paper,
              }}
            />
          </BladeFrame>
          <BladeFrame
            title="Fill Opacity"
            style={{ paddingLeft: '1.5rem', marginBottom: '1.5rem' }}
          >
            <Slider
              value={typeof fillOpacity === 'number' ? fillOpacity : 0}
              onChange={handleFillOpacitySliderChange}
              valueLabelDisplay="auto"
              min={0}
              max={100}
            />
            <TextField
              InputProps={{
                endAdornment: '%',
              }}
              type="number"
              value={typeof fillOpacity === 'number' ? fillOpacity : 0}
              onChange={handleFillOpacityInputChange}
              style={{
                marginLeft: '2rem',
                width: '130px',
                backgroundColor: theme.palette.background.paper,
              }}
            />
          </BladeFrame>

          <BladeFrame
            title="LineTension"
            style={{ paddingLeft: '1.5rem', marginBottom: '1.5rem' }}
          >
            <Slider
              value={typeof lineTension === 'number' ? lineTension : 0}
              onChange={handleLineTensionSliderChange}
              valueLabelDisplay="auto"
              min={0}
              max={10}
              step={0.1}
            />
            <TextField
              InputProps={{
                endAdornment: '',
              }}
              type="number"
              value={typeof lineTension === 'number' ? lineTension : 0}
              onChange={handleLineTensionInputChange}
              style={{
                marginLeft: '2rem',
                width: '130px',
                backgroundColor: theme.palette.background.paper,
              }}
            />
          </BladeFrame>

          <BladeFrame
            title="Logarithmic"
            style={{ paddingLeft: '1.5rem', marginBottom: '1.5rem' }}
          >
            <Switch
              value={scaleType}
              onChange={() => setScaleType(!scaleType)}
            />
          </BladeFrame>
        </CardContent>
      </Card>
      <div
        style={{ maxWidth: 720, width: '100%', height: 500, margin: '3rem' }}
      >
        {data?.chartData && data?.chartOptions && data?.chartData?.labels && (
          <Line data={data.chartData} options={data.chartOptions} />
        )}
      </div>
    </div>
  )
}
export default MGraph
