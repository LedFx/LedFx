import React, { useState, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardHeader from '@material-ui/core/CardHeader';
import CardContent from '@material-ui/core/CardContent';
import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
import { FormControl, Button } from '@material-ui/core';
import Select from '@material-ui/core/Select';
import CloudUploadIcon from '@material-ui/icons/CloudUpload';
import CloudDownloadIcon from '@material-ui/icons/CloudDownload';
import PowerSettingsNewIcon from '@material-ui/icons/PowerSettingsNew';
import AudioInputCard from './AudioInput'
import { getAudioInputs, setAudioInput, setConfig } from 'modules/settings';
import { Delete, Refresh } from '@material-ui/icons';
const useStyles = makeStyles({
    content: {
        display: 'flex',
        flexDirection: 'column',
    },
});

const GeneralCard = () => {

    const dispatch = useDispatch();
    const classes = useStyles();
    const [theme, setTheme] = useState(window.localStorage.getItem('blade') || 0);
    const settings = useSelector(state => state.settings)
    const { audioInputs } = settings;
    const changeTheme = event => {
        setTheme(event.target.value);
        window.localStorage.setItem('blade', event.target.value);
        window.location = window.location.href;
    };
    const onChangePreferredMode = (value) => {
        dispatch(setConfig({ config: { wled_preferred_mode: value } }))
    }
    const onChangeStartupScan = (value) => {
        dispatch(setConfig({ config: { scan_on_startup: value } }))
    }
    console.log(settings)
    useEffect(() => {
        dispatch(getAudioInputs())
    }, [dispatch])
    return (
        <Card style={{ marginBottom: '2rem' }}>
            <CardHeader title="General" subheader="Configure LedFx-Settings" />
            <CardContent className={classes.content}>
                {/* <FormControlLabel
                    control={
                        <Checkbox
                            name="scanAtStartup"
                        />
                    }
                    label="Scan for WLED on startup"
                />
                <FormControlLabel
                    value="scan"
                    control={<Switch color="primary" />}
                    label="Scan for WLED on startup"
                    labelPlacement="end"
                /> */}
                <AudioInputCard raw {...audioInputs} onChange={(e) => dispatch(setAudioInput(e))} />
                <FormControl>
                    <InputLabel id="wled-scan-selector">Scan for WLED on startup</InputLabel>
                    <Select
                        labelId="wled-scan-selector"
                        id="wled-scan-select"
                        value={settings.scan_on_startup}
                        onChange={(e) => onChangeStartupScan(e.target.value)}
                    >
                        <MenuItem value={true}>Yes</MenuItem>
                        <MenuItem value={false}>No</MenuItem>
                    </Select>

                </FormControl>
                <FormControl>
                    <InputLabel id="wled-mode-selector">Preferred WLED mode</InputLabel>
                    <Select
                        labelId="wled-mode-selector"
                        id="wled-mode-select"
                        value={settings.wled_preferred_mode}
                        onChange={(e) => onChangePreferredMode(e.target.value)}
                    >
                        <MenuItem value={"unset"}>Unset</MenuItem>
                        <MenuItem value={"E131"}>E131</MenuItem>
                        <MenuItem value={"DDP"}>DDP</MenuItem>
                    </Select>
                </FormControl>
                <FormControl>
                    <InputLabel id="theme-selector">Theme</InputLabel>
                    <Select
                        labelId="theme-selector"
                        id="theme-select"
                        value={theme}
                        onChange={changeTheme}
                    >
                        <MenuItem value={0}>Default</MenuItem>
                        <MenuItem value={1}>Dark</MenuItem>
                        <MenuItem value={2}>Blade</MenuItem>
                        <MenuItem value={3}>BladeDark</MenuItem>
                    </Select>
                </FormControl>
                {/* <Divider style={{ margin: '1rem 0' }} /> */}
                <Button
                    size="small"
                    startIcon={<CloudUploadIcon />}
                    variant="outlined"
                    style={{ marginTop: '1.5rem' }}
                >
                    Export Config
                </Button>
                <Button
                    size="small"
                    startIcon={<CloudDownloadIcon />}
                    variant="outlined"
                    style={{ marginTop: '0.5rem' }}
                >
                    Import Config
                </Button>
                <Button
                    size="small"
                    startIcon={<Delete />}
                    variant="outlined"
                    style={{ marginTop: '0.5rem' }}
                >
                    Reset Config
                </Button>
                <Button
                    size="small"
                    startIcon={<Refresh />}
                    variant="outlined"
                    style={{ marginTop: '0.5rem' }}
                >
                    Check Updates
                </Button>
                <Button
                    size="small"
                    startIcon={<PowerSettingsNewIcon />}
                    variant="outlined"
                    style={{ marginTop: '0.5rem' }}
                >
                    Shutdown
                </Button>
            </CardContent>
        </Card>
    );
};

export default GeneralCard;
