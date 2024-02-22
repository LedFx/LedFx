/* eslint-disable prettier/prettier */
import { useEffect, useRef, useState, FC } from 'react'
import { Box, Button, Dialog, DialogActions, DialogContent, MenuItem, Select, Typography } from '@mui/material'
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch'
import { transpose } from '../../../../utils/helpers'
import useStore from '../../../../store/useStore'
import useStyles from './M.styles'
import { MCell, clone, getMaxRange } from './M.utils'
import type { IMCell, IDir } from './M.utils'
import BladeFrame from '../../../../components/SchemaForm/components/BladeFrame'
import MWrapper from './MWrapper'
import MControls from './MControls'
import MFillSelector from './MFillSelector'
import MDialogTitle from './MDialogTitle'
import MSwitch from './MSwitch'
import MSlider from './MSlider'

const EditMatrix: FC<{ virtual: any }> = ({ virtual }) => {
  const classes = useStyles()
  const deviceRef = useRef<HTMLInputElement | null>(null)
  const devices = useStore((state) => state.devices)
  const [currentDevice, setCurrentDevice] = useState<string>('')
  const [rowN, setRowNumber] = useState<number>(virtual.config.rows || 4)
  const [colN, setColNumber] = useState<number>(Math.ceil(virtual.pixel_count/(virtual.config.rows || 1)) || 6)
  const [currentCell, setCurrentCell] = useState<[number, number]>([-1, -1])
  const [open, setOpen] = useState<boolean>(false)
  const [group, setGroup] = useState<boolean>(false)
  const [selectedPixel, setSelectedPixel] = useState<number | number[]>(0)
  const [direction, setDirection] = useState<IDir>('right')
  const [m, setM] = useState<IMCell[][]>(Array(rowN).fill(Array(colN).fill(MCell)))

  const [pixels, setPixels] = useState<any>([]);
  const pixelGraphs = useStore((state) => state.pixelGraphs);
  const virtuals = useStore((state) => state.virtuals);

  useEffect(() => {
    const handleWebsockets = (e: any) => {
      if (e.detail.id === virtual.id) {
        setPixels(e.detail.pixels);
      }
    };
    document.addEventListener('YZ', handleWebsockets);
    return () => {
      document.removeEventListener('YZ', handleWebsockets);
    };
  }, [virtuals, pixelGraphs]);

  const closeClear = () => {
    setOpen(false)
    setCurrentDevice('')
    setSelectedPixel(0)
    setGroup(false)
  }

  const handleDirectionChange = (d: IDir) => {
    setDirection(d)
    if (typeof selectedPixel !== 'number') {
      const [col, row] = currentCell
      const maxRange = getMaxRange(direction, row, col, rowN, colN)
      const distance = selectedPixel[1] - selectedPixel[0]
      if (distance > maxRange) {
        setSelectedPixel([selectedPixel[0], selectedPixel[0] + maxRange])
      }
    }
  }

  const assignPixels = () => {
    let updatedM: IMCell[][] = clone(m)
    const [col, row] = currentCell
    if (typeof selectedPixel === 'number') {
      updatedM[row][col] = { deviceId: currentDevice, pixel: selectedPixel }
    } else {
      for ( let index = 0; index < Math.abs(selectedPixel[1] - selectedPixel[0]); index += 1 ) {
        const newM = { deviceId: currentDevice, pixel: Math.min(selectedPixel[0], selectedPixel[1]) + index }
        if (direction.includes('right')) {
          if (direction.includes('flip')) {
            updatedM[row - Math.floor((index + col) / colN)][(index + col) % colN] = newM
          } else {
            updatedM[row + Math.floor((index + col) / colN)][(index + col) % colN] = newM
          }
        } else if (direction.includes('bottom')) {
          if (direction.includes('flip')) {
            updatedM[(index + row) % rowN][col - Math.floor((index + row) / rowN)] = newM
          } else {
            updatedM[(index + row) % rowN][col + Math.floor((index + row) / rowN)] = newM
          }
        } else if (direction.includes('left')) {
          if (direction.includes('flip')) {
            updatedM[row + Math.abs(Math.floor((col - index) / colN))][(colN + ((col - index) % colN)) % colN] = newM
          } else {
            updatedM[row - Math.abs(Math.floor((col - index) / colN))][(colN + ((col - index) % colN)) % colN] = newM
          }
        } else if (direction.includes('top')) {
          if (direction.includes('flip')) {
            updatedM[(rowN + ((row - index) % rowN)) % rowN][col + Math.abs(Math.floor((row - index) / rowN))] = newM
          } else {
            updatedM[(rowN + ((row - index) % rowN)) % rowN][col - Math.abs(Math.floor((row - index) / rowN))] = newM
          }
        }
      }
    }
    if (direction.includes('right-snake')) {
      if (direction.includes('flip')) {
        for (let i = row; i >= 0; i -= 1) {
          const currentRow = [...updatedM[i]]
          if ((i + row) % 2 === 1) updatedM[i] = currentRow.reverse()
        }
      } else {
        for (let i = row; i < rowN; i += 1) {
          const currentRow = [...updatedM[i]]
          if ((i + row) % 2 === 1) updatedM[i] = currentRow.reverse()
        }
      }
    }
    if (direction.includes('bottom-snake')) {
      if (direction.includes('flip')) {
        const mat = clone(updatedM)
        const temp = transpose(mat)
        for (let i = col; i >= 0; i -= 1) {
          const currentCol = [...temp[i]]
          if ((i + col) % 2 === 1) temp[i] = currentCol.reverse()
        }
        updatedM = transpose(temp)
      } else {
        const mat = clone(updatedM)
        const temp = transpose(mat)
        for (let i = col; i < colN; i += 1) {
          const currentCol = [...temp[i]]
          if ((i + col) % 2 === 1) temp[i] = currentCol.reverse()
        }
        updatedM = transpose(temp)
      }
    }
    if (direction.includes('left-snake')) {
      if (direction.includes('flip')) {
        for (let i = row; i < rowN; i += 1) {
          const currentRow = [...updatedM[i]]
          if ((i + row) % 2 === 1) updatedM[i] = currentRow.reverse()
        }
      } else {
        for (let i = row; i >= 0; i -= 1) {
          const currentRow = [...updatedM[i]]
          if ((i + row) % 2 === 1) updatedM[i] = currentRow.reverse()
        }
      }
    }
    if (direction.includes('top-snake')) {
      if (direction.includes('flip')) {
        const mat = clone(updatedM)
        const temp = transpose(mat)
        for (let i = col; i < colN; i += 1) {
          const currentCol = [...temp[i]]
          if ((i + col) % 2 === 1) temp[i] = currentCol.reverse()
        }
        updatedM = transpose(temp)
      } else {
        const mat = clone(updatedM)
        const temp = transpose(mat)
        for (let i = col; i >= 0; i -= 1) {
          const currentCol = [...temp[i]]
          if ((i + col) % 2 === 1) temp[i] = currentCol.reverse()
        }
        updatedM = transpose(temp)
      }
    }
    setM(updatedM)
    closeClear()
  }

  const handleSliderChange = ( e: Event, newPixelRange: number | [number, number], activeThumb: number ) => {
    if (typeof newPixelRange !== 'number') {
      const [col, row] = currentCell
      const maxRange = getMaxRange(direction, row, col, rowN, colN)
      const distance = Math.abs(newPixelRange[1] - newPixelRange[0])
      let adjustedLeftThumb = newPixelRange[0]
      let adjustedRightThumb = newPixelRange[1]
      if (distance > maxRange) {
        if (activeThumb === 0) {
          adjustedRightThumb = adjustedLeftThumb + maxRange
        } else {
          adjustedLeftThumb = adjustedRightThumb - maxRange
        }
      }
      const updatedSelectedPixel = direction === 'top' ? [adjustedRightThumb, adjustedLeftThumb] : [adjustedLeftThumb, adjustedRightThumb]
      setSelectedPixel(updatedSelectedPixel)
    } else {
      setSelectedPixel(newPixelRange)
    }
  }

  const clearPixel = () => {
    const updatedM = clone(m)
    const [col, row] = currentCell
    updatedM[row][col] = { deviceId: '', pixel: 0 }
    setM(updatedM)
    closeClear()
  }

  useEffect(() => {
    if (group) {
      if (typeof selectedPixel === 'number') {
        setSelectedPixel([selectedPixel, selectedPixel + 1])
      }
    } else if (typeof selectedPixel !== 'number') {
      setSelectedPixel(selectedPixel[0])
    }
  }, [group])

  useEffect(() => {
    setM(Array(rowN).fill(Array(colN).fill(MCell)))
  }, [rowN, colN])

  return <MWrapper>
    <MControls rowN={rowN} colN={colN} setRowNumber={setRowNumber} setColNumber={setColNumber} virtual={virtual} m={m} setM={setM} />
    <TransformWrapper centerZoomedOut minScale={0.1} initialScale={colN * 100 < window.innerWidth || rowN * 100 < window.innerHeight * 0.8 ? 1 : 0.1}>
      <TransformComponent>
        <div className={classes.gridCellContainer} style={{ width: colN * 100, height: rowN * 100 }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {m.map((yzrow, currentRowIndex) => <div key={`row-${currentRowIndex}`} style={{ display: 'flex' }}>
              {yzrow.map((yzcolumn: IMCell, currentColIndex: number) => (
                <Box key={`col-${currentColIndex}`} className={classes.gridCell} sx={{
                  backgroundColor: pixels && pixels[0] && pixels[0].length ? `rgb(${pixels[0][currentRowIndex*colN + currentColIndex]},${pixels[1][currentRowIndex*colN + currentColIndex]},${pixels[2][currentRowIndex*colN + currentColIndex]})` : '#222',
                  opacity: yzcolumn.deviceId !== '' ? 1 : 0.3,
                }} onContextMenu={(e) => {
                  e.preventDefault()
                  setCurrentCell([currentColIndex, currentRowIndex])
                  setCurrentDevice(yzcolumn.deviceId !== '' ? yzcolumn.deviceId : '')
                  setSelectedPixel(yzcolumn.pixel || 0)
                  setOpen(true)
                }}>
                  {yzcolumn.deviceId !== '' && (
                    <div className={classes.pixel}>
                      <Typography variant="caption">{devices[yzcolumn.deviceId].config.name}</Typography>
                      <Typography variant="caption">{yzcolumn.pixel}</Typography>
                    </div>
                  )}
                </Box>
              ))}
            </div>
            )}
          </div>
          <Dialog onClose={() => closeClear()} open={open} PaperProps={{ sx: { width: '100%', maxWidth: 320 } }}>
            <MDialogTitle currentCell={currentCell} m={m} />
            <DialogContent>
              <BladeFrame title="Device" style={{ marginBottom: '1rem' }}>
                <Select value={currentDevice} onChange={(e) => setCurrentDevice(e.target.value || '')} inputRef={deviceRef} variant="standard" fullWidth>
                  {devices &&
                    Object.keys(devices).map((d: any, i: number) => (
                      <MenuItem value={devices[d].id} key={i}>{devices[d].config.name}</MenuItem>
                    ))}
                </Select>
              </BladeFrame>
              {currentDevice && <>
                <MSwitch group={group} setGroup={setGroup} />
                {group && <MFillSelector direction={direction} onChange={handleDirectionChange} />}
                <MSlider group={group} devices={devices} currentDevice={currentDevice} selectedPixel={selectedPixel} handleSliderChange={handleSliderChange} />
              </>}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => clearPixel()}>Clear</Button>
              <Button onClick={() => assignPixels()}>Save</Button>
            </DialogActions>
          </Dialog>
        </div>
      </TransformComponent>
    </TransformWrapper>
  </MWrapper>}

export default EditMatrix
