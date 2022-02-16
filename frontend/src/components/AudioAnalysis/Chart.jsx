import React, { PureComponent } from 'react';
import moment from 'moment';
import { ComposedChart, ResponsiveContainer, XAxis, YAxis, Tooltip, Legend, Area } from 'recharts';

var momentDurationFormatSetup = require('moment-duration-format');
momentDurationFormatSetup(moment);

export default class Chart extends PureComponent {
    render() {
        const pitchClasses = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
        const pitchColors = [
            '#ff3333',
            '#ff9933',
            '#ffff33',
            '#99ff33',
            '#33ff33',
            '#33ff99',
            '#33ffff',
            '#3399ff',
            '#3333ff',
            '#9933ff',
            '#ff33ff',
            '#ff3399',
        ];

        const { segments, width, height, pitches } = this.props;
        return (
            <ResponsiveContainer width={width} height={height} debounce={5}>
                <ComposedChart
                    barGap={1}
                    data={segments}
                    margin={{
                        top: 15,
                        right: 20,
                        left: 0,
                        bottom: 0,
                    }}
                >
                    <XAxis
                        dataKey="start"
                        tickFormatter={time => {
                            let timeStr = time.toString().split('');
                            if (timeStr.includes('.')) {
                                const sec = timeStr
                                    .slice(
                                        0,
                                        timeStr.findIndex(el => el === '.')
                                    )
                                    .join('');
                                let milsec = timeStr
                                    .slice(timeStr.findIndex(el => el === '.') + 1)
                                    .join('');
                                if (milsec.length === 2) {
                                    milsec = milsec.concat('0');
                                } else {
                                    milsec = milsec.concat('00');
                                }
                                let t = moment.duration.format(
                                    [
                                        moment.duration({
                                            seconds: sec,
                                            milliseconds: milsec,
                                        }),
                                    ],
                                    'm:ss.S'
                                )[0];
                                return t.substring(0, t.length - 1);
                            } else {
                                return moment.duration.format(
                                    [
                                        moment.duration({
                                            seconds: time,
                                        }),
                                    ],
                                    'm:ss.S'
                                );
                            }
                        }}
                    />
                    <YAxis
                        tickFormatter={value => `${value.toFixed(0)}%`}
                        domain={[0, 100]}
                        allowDataOverflow="true"
                    />
                    <Tooltip
                        formatter={(value, name) =>
                            value > 6 ? [`${value.toFixed(0)}%`, name] : [null, null]
                        }
                        contentStyle={{ backgroundColor: '#0f0f0f', border: 'none' }}
                        labelStyle={{ color: '#f1f1f1' }}
                        itemSorter={item => -item.value}
                    />
                    <Legend align="left" height={250} layout="vertical" content={renderLegend} />
                    {pitchClasses.map((p, i) => {
                        if (pitches[p] === true) {
                            return (
                                <Area
                                    fillOpacity="1"
                                    strokeOpacity="1"
                                    name={p}
                                    stackId="1"
                                    stroke={pitchColors[i]}
                                    fill={pitchColors[i]}
                                    dataKey={s => s.pitches[i]}
                                />
                            );
                        }
                        return true;
                    })}

                    {/* Dynamically Painted Bar Chart */}
                    {/* <Bar dataKey={segments}>
                        {data.map((entry, index) => (
                            <Cell fill/>
                        ))}
                    </Bar> */}
                </ComposedChart>
            </ResponsiveContainer>
        );
    }
}

const renderLegend = props => {
    const payload = props;
    payload.payload.reverse();
    return (
        <ul style={{ height: 210, display: 'table', paddingLeft: 10, marginTop: 5 }}>
            {payload.payload.map((entry, index) => (
                <li key={`item-${index}`} style={{ color: entry.color, display: 'table-row' }}>
                    {entry.value}
                </li>
            ))}
        </ul>
    );
};
