import React from 'react';
import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Typography from '@material-ui/core/Typography';

// import EffectControlBlade from 'components/EffectControl/blade';

const MoreInfo = ({ display }) => {
    return (
        <>
            {' '}
            {/* {parseInt(window.localStorage.getItem('BladeMod')) > 2 && (
            <Grid item xs={12} lg={6}>
                <Card>
                    <CardContent>
                        <EffectControlBlade
                            display={display}
                            effect={effect}
                            schemas={schemas}
                            onClear={handleClearEffect}
                            onSubmit={handleSetEffect}
                            onTypeChange={handleTypeChange}
                        />
                    </CardContent>
                </Card>
            </Grid>
        )} */}
            <Grid item xs={6} lg={6}>
                <Card>
                    <CardContent>
                        <Typography variant="h5">Display Config</Typography>
                        <Typography variant="subtitle1">
                            Total Pixels: {display.config[display.id].pixel_count}
                        </Typography>
                        <br />
                        <Typography variant="caption">
                            Active: {JSON.stringify(display.config[display.id].active)}
                            <br />
                            Center Offset: {display.config[display.id].config.center_offset}
                            <br />
                            Crossfade: {display.config[display.id].config.crossfade}
                            <br />
                            Max Brightness: {display.config[display.id].config.max_brightness * 100 + '%'}
                            <br />
                            Preview only:{' '}
                            {JSON.stringify(display.config[display.id].config.preview_only)}
                        </Typography>
                    </CardContent>
                </Card>
            </Grid>
            <Grid item xs={6} lg={6}>
                <Card>
                    <CardContent>
                        <Typography variant="h5">Display Segments</Typography>
                        <Typography variant="subtitle1">
                            Segments: {display.config[display.id].segments.length}
                        </Typography>
                        <br />
                        {display.config[display.id].segments.map((s, i) => (
                            <li key={i}>{s.join(',')}</li>
                        ))}
                    </CardContent>
                </Card>
            </Grid>
        </>
    );
};

export default MoreInfo;
