try {
    def datahubUrl = "http://datahub-gms:8080/entities/v1/"
    // In Groovy, .text is a shorthand for a GET request
    def response = new URL(datahubUrl).getText(connectTimeout: 5000, readTimeout: 5000)
    
    execution.setVariable("datahubStatus", "Connected")
    println "Successfully contacted DataHub."
} catch (Exception e) {
    execution.setVariable("datahubStatus", "Connection Failed")
    println "Error: Could not reach DataHub: " + e.message
}