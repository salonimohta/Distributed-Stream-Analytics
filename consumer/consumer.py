from flask import Flask, Response, render_template, request,stream_with_context, flash, redirect, url_for, session,send_file
from kafka import KafkaConsumer,KafkaProducer
import cv2
import numpy as np
from datetime import datetime
import time
import json
from time import sleep
import base64
from flask_bootstrap import Bootstrap
from flask_wtf import Form
from wtforms.fields import DateTimeField
import imgToVideo
import os
import mysql.connector
from mysql.connector import errorcode


#List of camera
listOfCam = {
  "cam-01": ["webcamStream","/videomotionanalytics/webcam"],
  "cam-02": ["mobileCamStream","/videomotionanalytics/mobile"]
}

UPLOAD_FOLDER='videos/'


# Fire up the Kafka Consumer
topic1 = "distributed-video1"
topic2 = "distributed-video2"
topic3 = "webresolution"
topic4 = "mobileresolution"

producer = KafkaProducer(bootstrap_servers='localhost:9092',value_serializer=lambda x: json.dumps(x).encode('utf-8'))

consumer1 = KafkaConsumer(
    topic1, 
    bootstrap_servers=['localhost:9092'],
    value_deserializer=lambda m: json.loads(m.decode('utf-8')))

consumer2 = KafkaConsumer(
    topic2, 
    bootstrap_servers=['localhost:9092'],
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    max_partition_fetch_bytes=2097152)

fourcc = cv2.VideoWriter_fourcc(*'XVID')
webcamWriter=None
mobileCamWriter=None

webcamFlag=True
mobileCamFlag=True
recordWebFlag=False
recordMobFlag=False
webresolution='Auto'
mobileresolution='Auto'
showWebAnalyticsVideo=False
showMobileAnalyticsVideo=False
webcamImgArray=[]
mobileImgArray=[]
# Set the consumer in a Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key=os.urandom(24)
Bootstrap(app)

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login_validation', methods=['POST'])
def login_validation():
    uemail=request.form.get('email')
    upassword=request.form.get('password')

#create connection to DB
    try:
        cnx = mysql.connector.connect(host="localhost",user="root",password="Password123!",database="sem_project")
        cursor=cnx.cursor()
        cursor.execute("SELECT * FROM user WHERE email = %s  AND password = %s",(uemail,upassword))
        users=cursor.fetchall()
        print(users)
        if len(users)>0:
            session['user_id']=users[0][0]
            return redirect('/index')
        else:
            return redirect('/')

    except mysql.connector.Error as err:
        return (str(err))

@app.route('/route_to_streaming', methods=['POST','GET'])
def route_to_streaming():
    error = None
    cam_id=request.form.get('id')
    cam_id=cam_id.lower()
    if cam_id in listOfCam.keys():
        return redirect(url_for(listOfCam[cam_id][0]))
    else:
        error = "Enter valid camera id."
    return render_template('videostreaming.html',error=error)
 
@app.route('/route_to_analytics', methods=['POST'])
def route_to_analytics():
    cam_id=request.form.get('id')
    cam_id=cam_id.lower()
    startTime=request.form.get('start')
    endTime=request.form.get('end')
    global showWebAnalyticsVideo,webcamImgArray,showMobileAnalyticsVideo,mobileImgArray
    if endTime<startTime: 
        flash('The End time should be greater than the Start time')
    else:
        startDateTimeSplit=startTime.split(' ');
        endDateTimeSplit=endTime.split(' ');
        startDate=startDateTimeSplit[0];
        endDate=endDateTimeSplit[0];
        startTime=startDateTimeSplit[1].split(':')
        endTime=endDateTimeSplit[1].split(':')
        startSeconds=(int(startTime[0])*60+int(startTime[1]))*60+int(startTime[2]);
        endSeconds=(int(endTime[0])*60+int(endTime[1]))*60+int(endTime[2]);
        startTimestamp=(time.mktime(datetime.strptime(startDate,"%d-%m-%Y").timetuple())+startSeconds)*1000
        endTimestamp=(time.mktime(datetime.strptime(endDate,"%d-%m-%Y").timetuple())+endSeconds)*1000
        filename=cam_id+'--'+str(startTimestamp)+'-'+str(endTimestamp)+'.avi'
        print(filename)
        if listOfCam[cam_id][0]=="webcamStream":
            webcamImgArray=[]
            showWebAnalyticsVideo=True
            imgToVideo.findMotion(cam_id,startTimestamp,endTimestamp,webcamImgArray)
            if len(webcamImgArray)>0:
                return render_template('webcamMotionAnalytics.html',value=filename)
            else:
                flash('No motion has been detected in the selected time range')   
        
        elif listOfCam[cam_id][0]=="mobileCamStream":
            mobileImgArray=[]
            showMobileAnalyticsVideo=True
            imgToVideo.findMotion(cam_id,startTimestamp,endTimestamp,mobileImgArray)
            if len(mobileImgArray)>0:
                return render_template('mobileMotionAnalytics.html',value=filename)   
            else:
                flash('No motion has been detected in the selected time range')     
    return render_template('motiondetection.html')

@app.route('/index', methods=['GET'])
def index():
    if 'user_id' in session:
        return render_template('index.html')
    else:
        return redirect('/')

@app.route('/videostreaming', methods=['GET'])
def videoStreaming():
    return render_template('videostreaming.html')

@app.route('/videomotionanalytics', methods=['GET'])
def videoMotionAnalytics():
    return render_template('motiondetection.html')



@app.route('/videomotionanalytics/mobile', methods=['GET'])
def mobile_stream_analytics():
    global showMobileAnalyticsVideo,mobileImgArray
    if showMobileAnalyticsVideo==True:
        showMobileAnalyticsVideo=False
        return Response(
            stream_with_context(imgToVideo.stream_video(mobileImgArray)), 
            mimetype='multipart/x-mixed-replace; boundary=frame')
        
    return redirect(url_for('videoMotionAnalytics'))

@app.route('/videomotionanalytics/web', methods=['GET'])
def web_stream_analytics():
    global showWebAnalyticsVideo,webcamImgArray
    if showWebAnalyticsVideo==True:
        showWebAnalyticsVideo=False
        return Response(
            stream_with_context(imgToVideo.stream_video(webcamImgArray)), 
            mimetype='multipart/x-mixed-replace; boundary=frame')
    return redirect(url_for('videoMotionAnalytics'))

@app.route('/download-file/<filename>')
def download_files(filename):
    cameraId=filename.split('--')[0]
    file_path = UPLOAD_FOLDER + filename
    if cameraId=='cam-01':
        imgToVideo.convertToVideo(file_path,webcamImgArray,app.config['UPLOAD_FOLDER'])
    elif cameraId=='cam-02':
        imgToVideo.convertToVideo(file_path,mobileImgArray,app.config['UPLOAD_FOLDER'])
    
    return send_file(file_path, as_attachment=True, attachment_filename='')

@app.route('/videostreaming/webcam', methods=['GET','POST'])
def webcamStream():
    global webcamFlag,recordWebFlag,webcamWriter,webresolution
    if request.method == 'POST':
        if request.form['submit']=='Stop' and webcamFlag==True:
            webcamFlag=False
        elif request.form['submit']=='Start' and webcamFlag==False:
            webcamFlag=True
        elif request.form['submit']=='Start Recording' and recordWebFlag==False:
            recordWebFlag=True
            time=str(datetime.now().time())
            filename='./recording-WEBCAM--'+time+'.avi'
            webcamWriter = cv2.VideoWriter(filename,fourcc, 5.0, (640,480),1)
        elif request.form['submit']=='Stop Recording' and recordWebFlag==True:
            recordWebFlag=False
            webcamWriter.release()
        elif request.form['submit'] in ['720p','480p','360p','240p','Auto']:
            if webresolution!=request.form['submit']:
                if recordWebFlag==True:
                    webcamWriter.release()
                    time=str(datetime.now().time())
                    filename='./recording-WEBCAM--'+time+'@'+request.form['submit']+'.avi'
                    webcamWriter=cv2.VideoWriter(filename,fourcc,5.0,(640,480),1)
                webresolution=request.form['submit']
                producer.send(topic3,webresolution)
    
    return render_template('webcamStream.html')



@app.route('/videostreaming/mobile', methods=['GET','POST'])
def mobileCamStream():
    global mobileCamFlag,recordMobFlag,mobileCamWriter,mobileresolution
    if request.method == 'POST':
        print(request.form['submit']=='Start')
        if request.form['submit']=='Stop' and mobileCamFlag==True:
            mobileCamFlag=False
        elif request.form['submit']=='Start' and mobileCamFlag==False:
            mobileCamFlag=True
        if request.form['submit']=='Start Recording' and recordMobFlag==False:
            recordMobFlag=True
            time=str(datetime.now().time())
            filename='./recording-MOBILE--'+time+'.avi'
            mobileCamWriter = cv2.VideoWriter(filename,fourcc,5.0, (640,480),1)
        elif request.form['submit']=='Stop Recording' and recordMobFlag==True:
            recordMobFlag=False
            mobileCamWriter.release()
        elif request.form['submit'] in ['720p','480p','360p','240p','Auto']:
            if mobileresolution!=request.form['submit']:
                if recordMobFlag==True:
                    mobileCamWriter.release()
                    time=str(datetime.now().time())
                    filename='./recording-MOBILE--'+time+'@'+request.form['submit']+'.avi'
                    mobileCamWriter=cv2.VideoWriter(filename,fourcc,5.0,(640,480),1)
                mobileresolution=request.form['submit']
                producer.send(topic4,mobileresolution)

            
    return render_template('mobileStream.html')

@app.route('/webcam_feed', methods=['GET'])
def video_feed_web():
    """
    This is the heart of our video display. Notice we set the mimetype to 
    multipart/x-mixed-replace. This tells Flask to replace any old images with 
    new values streaming through the pipeline.
    """
    global webcamFlag
    #print(webcamFlag)
    if webcamFlag:
        return Response(
            stream_with_context(get_video_stream(consumer1,webcamWriter,recordWebFlag)), 
            mimetype='multipart/x-mixed-replace; boundary=frame')

    return Response()


@app.route('/mobile_feed', methods=['GET'])
def video_feed_mobile():
    """
    This is the heart of our video display. Notice we set the mimetype to 
    multipart/x-mixed-replace. This tells Flask to replace any old images with 
    new values streaming through the pipeline.
    """
    global mobileCamFlag
    #print(mobileCamFlag)
    if mobileCamFlag:
        return Response(
            stream_with_context(get_video_stream(consumer2,mobileCamWriter,recordMobFlag)), 
            mimetype='multipart/x-mixed-replace; boundary=frame')

    return Response()

def get_video_stream(consumer,outFile,flag):
    """
    Here is where we recieve streamed images from the Kafka Server and convert 
    them to a Flask-readable format.
    """
    for msg in consumer:
        decodedFrame=base64.b64decode(msg.value['data'])
        image = np.fromstring(decodedFrame, dtype=np.uint8)
        #print(decodedFrame)
        image = np.reshape(image, (480, 640, 3))
        #print(image)
        ret, frame = cv2.imencode('.jpg', image)
        #print(frame.tobytes() == decodedFrame)
        buf = frame.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpg\r\n\r\n' + buf + b'\r\n\r\n')
        if flag==True:
            #image = np.fromstring(decodedFrame, dtype=np.uint8)
            #image = cv2.imdecode(image, cv2.IMREAD_COLOR)
            #print(image)
            outFile.write(image)
        #sleep(0.07)
  
@app.route('/logout')
def logout():
    session.pop('user_id')
    return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)


