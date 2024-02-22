const PadTitle = ({ label }: any) => (
  <h3>
    {label.split(' (')[0]}
    <br />
    {`(${label.split(' (')[1]}`}
  </h3>
)

export default PadTitle
