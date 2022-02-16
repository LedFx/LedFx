import React, { PureComponent } from 'react';
import { ComposedChart, ResponsiveContainer, XAxis, YAxis, Bar, Cell, Legend } from 'recharts';

export default class Chart extends PureComponent {
    render() {
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

        const { sections, width } = this.props;
        return (
            <ResponsiveContainer width={width} height={20} debounce={5}>
                <ComposedChart
                    barGap={1}
                    data={sections}
                    margin={{
                        top: 15,
                        right: 20,
                        left: 0,
                        bottom: 0,
                    }}
                >
                    <XAxis hide="true" dataKey="start" unit="s" />
                    <YAxis hide="true" height={10} />
                    <Legend align="left" height={20} layout="vertical" content={renderLegend} />
                    {/* <Tooltip 
                        content={renderTooltip}
                    /> */}
                    <Bar dataKey="start" minPointSize={10} barGap={0}>
                        {sections
                            ? sections.map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={pitchColors[entry.key]} />
                              ))
                            : null}
                    </Bar>
                </ComposedChart>
            </ResponsiveContainer>
        );
    }
}

const renderLegend = () => {
    return (
        <ul
            style={{
                height: 20,
                display: 'table',
                paddingLeft: 10,
                marginTop: 0,
                listStyleType: 'none',
            }}
        >
            <li style={{ color: '#f1f1f1' }}>Key</li>
        </ul>
    );
};

// const renderTooltip = ({ active, payload, label }) => {
//     const pitchClasses = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
//     if (active === true) {
//         return  (
//             <div style={{backgroundColor: '#010101', padding: 10}}>
//                 <div style={{color:'#f1f1f1'}}>{`${pitchClasses[payload[0].payload.key]}`}</div>
//             </div>
//         )
//     }
// }
