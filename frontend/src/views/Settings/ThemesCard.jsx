import React, { useState } from 'react';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardHeader from '@material-ui/core/CardHeader';
import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
import FormControl from '@material-ui/core/FormControl';
import Select from '@material-ui/core/Select';

const ThemesCard = () => {
    const [theme, setTheme] = useState(window.localStorage.getItem('blade') || 0);

    const changeTheme = event => {
        setTheme(event.target.value);
        window.localStorage.setItem('blade', event.target.value);
        window.location = window.location.href;
    };
    return (
        <Card>
            <CardHeader title="UI-Settings" subheader="Customize the appearance of LedFx" />
            <CardContent>
                <FormControl>
                    <InputLabel id="theme-selector">Theme</InputLabel>
                    <Select
                        labelId="theme-selector"
                        id="theme-select"
                        value={theme}
                        onChange={changeTheme}
                    >
                        <MenuItem value={0}>Original</MenuItem>
                        <MenuItem value={1}>OriginalDark</MenuItem>
                        <MenuItem value={2}>BladeLight</MenuItem>
                        <MenuItem value={3}>BladeDark</MenuItem>
                        <MenuItem value={4}>GreenLight</MenuItem>
                        <MenuItem value={5}>GreenDark</MenuItem>
                        <MenuItem value={6}>BlueLight</MenuItem>
                        <MenuItem value={7}>BlueDark</MenuItem>
                    </Select>
                </FormControl>
            </CardContent>
        </Card>
    );
};

export default ThemesCard;
