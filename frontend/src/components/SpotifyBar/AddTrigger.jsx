import React, { Component } from 'react'
import { getPresets, addTrigger } from '../../actions'
import { connect } from 'react-redux'
import { MenuItem, Select, FormControl, FormControlLabel, InputLabel, Checkbox, Grid, withStyles, Button } from '@material-ui/core'

const styles = (theme) => ({
    presetSelect: {
        color: '#1ED760',
    },
    label: {
        color: '#1ED760'
    },
    submitButton: {
        backgroundColor: '#1ED760'
    },
    icon: {
        fill: '#1ED760',
    },
    note: {
        margin: 0,
        color: '#1ED760'
    },
    underline: {
        borderBottom: '#1ED760'
    }
})

export class AddTrigger extends Component {
    constructor(props) {
        super(props)
        this.state = {
            selectedPreset: 'Select',
            checked: false
        }
        this.handleSelectChange = this.handleSelectChange.bind(this);
        this.handleCheckChange = this.handleCheckChange.bind(this);
        this.handleSubmit = this.handleSubmit.bind(this);
    }

    handleSelectChange(e) {
        this.setState({selectedPreset: e.target.value})
    }

    handleCheckChange(e) {
        this.setState({checked: e.target.checked})
    }

    handleSubmit(id, songID, songName, checked, songPosition) {
        if (checked == true) {
            this.props.addTrigger(id, songID, songName, songPosition)
        } else {
            this.props.addTrigger(id, songID, songName)
        }
    }

    componentDidMount = () => {
        this.props.getPresets()
    }

    render() {
        const {classes} = this.props
        return (
            <Grid container justify='flex-end' spacing='3'>
                <Grid container item xs='12' sm='4' justify='center' alignItems='center'>
                    <FormControl>
                        <InputLabel className={classes.label} id="preset-select">Preset</InputLabel>
                        <Select 
                            inputProps={{classes: {icon: classes.icon}}} 
                            className={classes.presetSelect} 
                            labelId='preset-select' 
                            value={this.state.selectedPreset} 
                            onChange={this.handleSelectChange}>
                            {renderPresetsMenu(this.props.presets)}
                        </Select>
                    </FormControl>
                </Grid>
                <Grid container item xs='6' sm='3' justify='center' alignItems='center' direction='column'>
                    <FormControl>
                        <FormControlLabel 
                            style={{color: '#1ED760'}} 
                            label='Song Position' 
                            control={<Checkbox style={{color: '#1ED760'}} 
                            checked={this.state.checked} 
                            onChange={this.handleCheckChange}/>}
                        />
                    </FormControl>
                </Grid>
                <Grid container item xs='6' sm='3' justify='center' alignItems='center'>
                    <Button 
                        variant='contained' 
                        onClick={() =>  this.handleSubmit(this.state.selectedPreset, this.props.trackState.id, this.props.trackState.name, this.state.checked, this.props.position)}
                        className={classes.submitButton}
                        >Add Trigger
                    </Button>
                </Grid>
            </Grid>
        )
    }
}

const renderPresetsMenu = (presets) => Object.keys(presets).map((key) => (<MenuItem value={key}>{key}</MenuItem>))


const mapStateToProps = state => ({ 
    presets: state.presets 
})

const mapDispatchToProps = (dispatch) => ({
    getPresets: () => dispatch(getPresets()),
    addTrigger: (id, songID, songName, songPosition) => dispatch(addTrigger(id, songID, songName, songPosition))
})

export default connect(mapStateToProps, mapDispatchToProps)(withStyles(styles)(AddTrigger))