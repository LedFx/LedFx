import React from 'react';
import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
import FormHelperText from '@material-ui/core/FormHelperText';
import FormControl from '@material-ui/core/FormControl';
import Select from '@material-ui/core/Select';
import DeleteIcon from '@material-ui/icons/Delete';
import { Slider, Switch } from '@material-ui/core';

const marks = [
    {value: 1, label: '1',},
    {value: 255, label: '255',},
  ];

export default function ThisDropDown(props) {
    return (
        <>
            <FormControl>
                <InputLabel htmlFor="grouped-select">Then Do This</InputLabel>
                    <Select
                        labelId="demo-simple-select-helper-label"
                        id="demo-simple-select-helper"
                        name="qlc_payload"
                        // value={props.value}
                        onChange={(event)=>props.handleDropTypeChange(event,props.idx)}
                    >
                    {props.QLCWidgets && props.QLCWidgets.length > 0 && props.QLCWidgets.map((e,f)=>
                        <MenuItem key={f} value={e}>
                                ID: {e[0]}, Type: {e[1]}, Name: {e[2]}
                        </MenuItem>)
                    }
                    </Select>
                <FormHelperText>Some important helper text</FormHelperText>
            </FormControl>
            <button variant="contained" color="primary" onClick={()=>props.handleTypeRemoveDropDown(props.idx)}><DeleteIcon/></button>
            <div style={{ minWidth: '150px' }}></div>
            {props.showSwitch && <label>QLC+ widget selected above (On/Off) </label>}
            {props.showSwitch && 
            <Switch 
                color="primary"
                name={props.value}
                checked={props.switchValue}
                onChange={(event)=>props.handleDropTypeChange(event,props.idx)}
            />
            }
            <div style={{ minWidth: '150px' }}>
                {props.showSlider &&<label>QLC Slider Widget Value</label>}
                {props.showSlider &&<Slider
                    aria-labelledby="discrete-slider"
                    valueLabelDisplay="auto"
                    marks={marks}
                    step={1}
                    min={0}
                    max={255}
                    defaultValue={1}
                    onChange={(event,value)=>props.handleDropTypeChange(event,props.idx,value,props.value)}
                />}
            </div> 
        </>
    );
  }

