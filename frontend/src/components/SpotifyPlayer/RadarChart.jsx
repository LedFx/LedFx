import React, { useState, useEffect, useContext } from 'react';
import styled from 'styled-components';
import { Radar } from 'react-chartjs-2';

const RadarChartContainer = styled.div`
    width: 500px;
    height:'500px;

    h2 {
        margin-bottom: 40px;
        font-family: Inter;
        font-style: normal;
        font-weight: 900;
        font-size: 18px;
        color: white;
    }
`;

export default function RadarChart(props) {
    const [chartValues, setChartValues] = useState(
        props.chartValues
            ? [
                  props.chartValues.energy,
                  props.chartValues.danceability,
                  props.chartValues.valence,
                  props.chartValues.instrumentalness,
                  props.chartValues.loudness,
              ]
            : []
    );
    const [chartData, setChartData] = useState(props.chartData || []);

    useEffect(() => {
        if (props.paused) {
            setChartData(props.chartData);
            setChartValues([
                props.chartValues.energy,
                props.chartValues.danceability,
                props.chartValues.valence,
                props.chartValues.instrumentalness,
                props.chartValues.loudness,
            ]);
        }
    }, [props]);

    const chart = () => {
        setChartData({
            labels: ['Energy', 'Danceability', 'Positiveness', 'Instrumentalness', 'Loudness'],
            datasets: [
                {
                    data: chartValues,
                    backgroundColor: 'rgba(50, 246, 152, 0.5)',
                    borderColor: 'rgb(0, 226, 123)',
                    borderWidth: 3,
                    pointBackgroundColor: 'rgb(50, 246, 152)',
                    pointBorderWidth: 2,
                    fontColor: '#fff',
                },
            ],
        });
    };

    const chartOptions = {
        responsive: true,
        legend: {
            display: false,
        },

        layout: {
            padding: {
                left: 0,
                right: 0,
                top: 0,
                bottom: 0,
            },
        },
        scale: {
            ticks: {
                callback: function () {
                    return '';
                },
                backdropColor: 'rgba(0, 0, 0, 0)',
                min: -10,
                max: 10,
            },
            pointLabels: {
                fontColor: 'black',
            },
            gridLines: {
                color: '#009688',
            },
            angleLines: {
                color: '#009688',
            },
        },
        tooltips: {
            callbacks: {
                label: function (tooltipItem) {
                    return tooltipItem.yLabel;
                },
            },
        },
    };

    useEffect(() => {
        if (window.innerWidth <= 768) {
            chartOptions.aspectRatio = 1;
        } else {
            chartOptions.aspectRatio = 2;
        }
        chart();
    }, [chartValues]);

    return (
        <RadarChartContainer>
            {/* <h2>Curate Your Playlist</h2> */}
            <Radar data={chartData} height={null} width={null} options={chartOptions} />
        </RadarChartContainer>
    );
}
