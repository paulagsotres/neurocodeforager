import EMDlib as emd
import multiprocessing as mp
import scipy.signal as sig
import numpy as np
import time as time
import sys as sys
import os as os
from sklearn.externals import joblib

freqs = np.arange(10,200)
nPCs = 5
matchSessions = False
dimrec = 'ica'
lfpSR = 1250.

def run(base,ChLabels,sessions,freqs=freqs,nPCs=nPCs,matchSessions=matchSessions,dimrec=dimrec,nWorkers=0):

	if nWorkers>3*mp.cpu_count()/4:
		nWorkers = 3*mp.cpu_count()/4
	if nWorkers<1:
		nWorkers = mp.cpu_count()/3

	print
	print(bold('Computing tSCs for ')+base)

	printaux = '             '+bold('SESSIONS: ')
	for s in sessions:
		printaux += str(s)+', '
	printaux = printaux[0:-2]
	print(printaux)

	printaux = '             '+bold('CHANNELS: ')
	for c in ChLabels:
		printaux += str(c)+', '
	printaux = printaux[0:-2]
	print(printaux)
	print

	for s in sessions:
		print('...... identifying theta cycles (includes EMD) from session #'+str(s))
		baseS = base+'_'+str(s)
		for ChLabel in ChLabels:
			print('......... running channel #'+str(ChLabel))
			printTime('............. started at: ')
			runEMD(baseS,ChLabel,lfpSR=lfpSR,nWorkers=nWorkers)
			writeThetaInfo(baseS,ChLabel)
			printTime('............. done at: ')

	for ChLabel in ChLabels:
		print('...... extracting tSCs for channel #'+str(ChLabel))
		printTime('............. started at: ')
		runThetaSC(base,ChLabel,[ChLabel],sessions,freqs=freqs,nPCs=nPCs,matchSessions=matchSessions,dimrec=dimrec)
		printTime('............. done at: ')
	
	print('All done!')
		
#########################################################################################################
#### FUNCTIONS FOR TSC EXTRATION ########################################################################
#########################################################################################################

def GetCyclePSD(CycleEdges,WVSpect):    
    
	nCycles = np.size(CycleEdges,0)
	CyclePSD = np.zeros((nCycles,np.size(WVSpect,0)))
	for cyclei in range(nCycles):
		samples = range(CycleEdges[cyclei,0],CycleEdges[cyclei,1])
		CyclePSD[cyclei,:] = np.mean(WVSpect[:,samples],axis=1)
        
	return CyclePSD

def runThetaSC(base,thetaCh,spectCh,sessions,freqs=freqs,nPCs=nPCs,matchSessions=matchSessions,dimrec=dimrec):

	nSessions = len(sessions)

	cycleSpeed = [None]*nSessions
	spectralSigs = [None]*nSessions
	print('................ computing single cycle spectral signatures')
	for (si,s) in enumerate(sessions):

		baseSession = base+'_'+str(s)

		filename = baseSession+'.theta.cycles.'+str(thetaCh)
		thetacycles = np.load(filename)

		edges = thetacycles[:,np.array([0,4])]
		nCycles = len(edges)

		cyclePSDs = np.array([]).reshape(nCycles,0)
		for ChLabel in spectCh:
			WVspect4ICA = computeWVspect4ICA(baseSession,ChLabel,freqs)
			cyclePSDs = np.concatenate((cyclePSDs,GetCyclePSD(edges,WVspect4ICA)),axis=1)
		del WVspect4ICA
		
		spectralSigs[si] = cyclePSDs

	if matchSessions:
		nCyclesPerSession = np.min([len(spectralSigs[i]) for i in range(nSessions)])

	nFeatures = np.size(spectralSigs[0],1)
	spectralSigs0 = np.array([]).reshape((0,nFeatures)) # concatenated spectral signatures
	for sessioni in range(nSessions):

		nCy = np.size(spectralSigs[sessioni],0)
		cycleIds = np.arange(nCy)
		if matchSessions:		
			if sessioni<1:
				cycleIds = np.arange(nCy,nCy-nCyclesPerSession,-1)
			else:
				cycleIds = np.arange(nCyclesPerSession)

		spectralSigs0 = np.vstack((spectralSigs0,spectralSigs[sessioni][cycleIds,:])) 

	print('................ extracting tSCs')
	model = extractPatterns(spectralSigs0,dimrec,nPCs,nreplicates=50)

	nChs = len(spectCh)
	efreqs = np.squeeze(np.matlib.repmat(freqs,1,nChs))

	projections = model.transform(spectralSigs0).T

	componentMainFreq = np.zeros(model.n_components)
	highfreqScore = np.zeros((model.n_components))
	for compi in range(model.n_components):
		        
		meanproj = np.mean(projections[compi,:])
		compsign = np.sign(meanproj)  
		component = np.copy(model.components_[compi,:])
		compnorm = np.sqrt(np.sum(pow(component,2))) 
		component /= compnorm
                        
		highfreqIds = np.where(efreqs>100)[0]
	        highfreqscore = np.abs(np.sum(component[highfreqIds])) # gets contribution from high-freqs (>100)
	        baselinescore = np.abs(np.sum(component[efreqs<100])) # gets contribution from low-freqs (<100)
		highfreqScore[compi] = np.sum(np.abs(component[highfreqIds]))/np.sum(np.abs(component))

		# gets frequency with larger weight
		meanComponent = np.mean(pow(component,2).reshape(nChs,len(freqs)),axis=0)
		preakfreqi = np.argmax(meanComponent)

		# define such frequency as the main freq of that pattern
		componentMainFreq[compi] = freqs[preakfreqi]

		proj = projections[compi,:]
		stdproj = np.std(proj)
		meanproj = np.mean(proj)
		if (pow(meanproj,2)/pow(stdproj,2))<.5:
			compsign = np.sign(np.sum(component[efreqs<100]))
			component =  component*compsign
			meanComponent = np.mean(pow(component,2).reshape(nChs,len(freqs)),axis=0)
			preakfreqi = np.argmax(meanComponent)
			componentMainFreq[compi] = freqs[preakfreqi]
			model.components_[compi,:] *= compsign

	hfComponent = np.argmax(highfreqScore)
	component = np.copy(model.components_[hfComponent,:])
	model.components_[hfComponent,:] =  component*np.sign(np.sum(component[highfreqIds]))
	meanComponent = np.mean(pow(model.components_[hfComponent,:],2).reshape(nChs,len(freqs)),axis=0)
	highfreqIds = np.where(freqs>100)[0]
	preakfreqi = np.argmax(meanComponent[highfreqIds])	
	componentMainFreq[hfComponent] = freqs[highfreqIds[preakfreqi]]

	print('................ saving theta profiles for '+base)
	output = {}
	for (si,s) in enumerate(sessions):

		baseSession = base+'_'+str(s)

		filename = baseSession+'.tSCs.'+dimrec+'.'+str(thetaCh)

		output = {}
		output['tSCs'] = (model.components_).T
		output['mainfreqs'] = componentMainFreq
		output['projections'] = model.transform(spectralSigs[si])
		output['cyclePSDs'] = spectralSigs[si]
		output['freqs'] = freqs
		output['efreqs'] = efreqs
		output['thetaCh'] = thetaCh
		output['ChLabels'] = spectCh

		fileout = open(filename, 'wb')	
		np.save(fileout,output)
		fileout.close()

		filename = baseSession+'.tSCs.'+dimrec+'.model'+'.'+str(thetaCh)
		joblib.dump(model, filename) 

	printTime('... done at: ')

def extractPatterns(data,dimrec,nPCs,nreplicates=50):

	if dimrec is 'ica':
		from sklearn.decomposition import FastICA
		model = FastICA(n_components=nPCs)
	if dimrec is 'nmf':
		from sklearn.decomposition import NMF
		model = NMF(n_components=nPCs, init='random', random_state=0)

	cs = np.zeros(nreplicates)
	candidatePatterns = [None]*nreplicates
	for runi in range(nreplicates):
		aux = model.fit(data).transform(data)
		c = np.corrcoef(pow(aux,2).T)
		cs[runi] = np.mean(np.abs(c-np.diag(np.diag(c))))
		candidatePatterns[runi] = np.copy(model)
	model = np.copy(candidatePatterns[np.argmin(cs)]).item()

	return model

#########################################################################################################
#########################################################################################################

#########################################################################################################
#### EMD ################################################################################################
#########################################################################################################

def eemd(signal,nWorkers,nEnsembles,NoiseStd = 0.3,NumShifts=10):

        nEnsemblesPerWorker = int(np.ceil(nEnsembles/nWorkers))

        EMDparOut = mp.Queue()
        processes = [mp.Process(target=emdpar,args=(signal,nEnsemblesPerWorker,EMDparOut,NoiseStd,NumShifts)) \
                        for i in range(nWorkers)]
        for p in processes:
                p.start()
        emdjoin = [EMDparOut.get() for p in processes] 
        for p in processes:
                p.join()       
        imfs = np.zeros((np.shape(emdjoin[0])))
        for i in range(len(emdjoin)):
                imfs += emdjoin[i]
        imfs = imfs/nWorkers

        return imfs

def emdpar(signal,nEnsembles,EMDparOut,NoiseStd=0.35,NumShifts=10):
        np.random.seed()
        imf = emd.eemd(signal,NoiseStd,nEnsembles,NumShifts)
        EMDparOut.put(imf)

def runEMD(baseS,ch,lfpSR=lfpSR,nWorkers=2,nEnsembles=100):

	imfs = None

	def processIMFs(imfs,lfpSR):

		iF,iA,iP = emd.calc_inst_info(imfs,lfpSR)

		filename = baseS+'.emd.if.'+str(ch)
		output = open(filename, 'wb')
		np.save(output,iF)
		output.close()

		filename = baseS+'.emd.ia.'+str(ch)
		output = open(filename, 'wb')
		np.save(output,iA)
		output.close()

	nEnsembles = nWorkers*(nEnsembles/nWorkers)
	if nEnsembles<50:
		nEnsembles = 50

	if os.path.exists(baseS+'.emd.'+str(ch)):
		print('................ emd for '+baseS+'.emd.'+str(ch)+' already in disk. Will not recompute.')
	else:
		filename = baseS+'.eeg.'+str(ch)
		lfp = np.load(filename)
		imfs = eemd(lfp,nWorkers,nEnsembles,NoiseStd = 0.3,NumShifts=10)

		filename = baseS+'.emd.'+str(ch)
		output = open(filename, 'wb')
		np.save(output,imfs)
		output.close()

	if (not(os.path.exists(baseS+'.emd.if.'+str(ch))))|(not(os.path.exists(baseS+'.emd.ia.'+str(ch)))):
		if imfs is None:
			imfs = np.load(baseS+'.emd.'+str(ch))
		processIMFs(imfs,lfpSR)

#########################################################################################################
#########################################################################################################

#base = '/vitors_directory/data/mst158-1809-0124'
#ChLabel = 4
#baseS = base+'_'+'2'


#########################################################################################################
#### DEFINING THETA CYCLES ##############################################################################
#########################################################################################################

def writeThetaInfo(baseSession,ChLabel):

	thetaCycles,phase,thetaAmp = runThetaCycles(baseSession,ChLabel)

	filename = baseSession+'.theta.cycles.'+str(ChLabel)
	output = open(filename, 'wb')
	np.save(output,thetaCycles)
	output.close()

	filename = baseSession+'.theta.phase.'+str(ChLabel)
	output = open(filename, 'wb')
	np.save(output,phase)
	output.close()

	filename = baseSession+'.theta.cycleamp.'+str(ChLabel)
	output = open(filename, 'wb')
	np.save(output,thetaAmp)
	output.close()

def runThetaCycles(baseSession,ChLabel):

	ChLabel = str(ChLabel)

	filename = baseSession+'.emd.'+ChLabel
	imf = np.load(filename)

	mainfreqs = getIMFmainfreq(baseSession,ChLabel)
	validIMFs = np.where(~(np.isnan(mainfreqs)))[0]

	thetaIMFs = validIMFs[(mainfreqs[validIMFs]>=5)&(mainfreqs[validIMFs]<17)]
	theta = np.sum(imf[thetaIMFs,:],axis=0)

	lowfreqs = validIMFs[mainfreqs[validIMFs]<5]
	lowfreqenv = np.abs(runHilbert(np.sum(imf[lowfreqs,:],axis=0)))

	cycleRefs = defineThetaCycles(theta,lowfreqenv)
	del lowfreqenv

	phase = getThetaPhases(cycleRefs,len(theta))

	thetaEnv = np.abs(runHilbert(theta))
	del theta
	nCycles = np.size(cycleRefs,0)
	thetaAmp = np.zeros(nCycles)
	for cyclei in range(nCycles):
		thetaAmp[cyclei] = np.mean(thetaEnv[cycleRefs[cyclei,0]:cycleRefs[cyclei,-2]])

	return cycleRefs,phase,thetaAmp

def getIMFmainfreq(baseSession,ChLabel):

        filename = baseSession+'.emd.if.'+str(ChLabel)
        IF = np.load(filename)

        filename = baseSession+'.emd.ia.'+str(ChLabel)
        IA = np.load(filename)

        nimfs = np.size(IA,0)

	mainfreqs = np.zeros(nimfs)+np.nan
	for imfi in range(1,nimfs-1):

		if0 = np.copy(IF[imfi,1:-1])
		ia0 = np.copy(IA[imfi,1:-1])

		mainfreqs[imfi] = np.sum(if0*pow(ia0,2))/np.sum(pow(ia0,2))

	return mainfreqs

def defineThetaCycles(Theta,lowFreqAmp,SamplingRate=1250.):

	###################################################################################################
	# STEP 1. Define some parameters ################################################################
	# below define what is be the minimum peak to peak (and valley to valley) interval allowed
	MinPeak2PeakDistance = int(round((1./12)*SamplingRate)) # I use a 12-Hz cycle

	# below define what is be the maximum peak to peak (and valley to valley) interval allowed
	MaxPeak2PeakDistance = int(round((1./5)*SamplingRate)) # I use a 5-Hz cycle

	# below define what is the maximum and minimum peak to valley internval
	MinPeak2ValleyDistance = int(round((1./16)*SamplingRate/2)) # 16-Hz half-cycle for minimum 
	MaxPeak2ValleyDistance = int(round((1./4)*SamplingRate/2)) # 4-Hz half-cycle for maximum

	###################################################################################################
	# STEP 2. Define thresholds for peak detection ####################################################

	# I use two threholds.

	# FIRST THRESHOLD is based on slow oscillations oscillations. 
	# The rationale is that we want real theta oscillations and not 1/f signals. 
	# So theta peaks have to be larger than low-frequency amplitudes.

	lowfreqthrs = np.copy(lowFreqAmp)

	# SECOND THRESHOLD is a fixed (arbitrary) threshold
	# I'm looking still for a better definition.
	MinThetaPeakAmplitude = np.median(np.abs(Theta))
	# this is to avoid to get periods where the signal is (nearly) flat

	# line below combines both thresholds
	lowfreqthrs[lowfreqthrs<MinThetaPeakAmplitude] = MinThetaPeakAmplitude	

	###################################################################################################
	# STEP 3. Theta peak and valley detection #########################################################

	# I use this function for peak detection. It is in ddLab
	PeakIs = detectPeaks(Theta,show=False,mph=MinThetaPeakAmplitude,mpd=MinPeak2PeakDistance)
	ValleyIs = detectPeaks(-Theta,show=False,mph=MinThetaPeakAmplitude,mpd=MinPeak2PeakDistance)

	# then, take only peaks and valleys that pass amplitude thresholds
	PeakIs = PeakIs[Theta[PeakIs]>=lowfreqthrs[PeakIs]]
	ValleyIs = np.unique(ValleyIs[Theta[ValleyIs]<=-lowfreqthrs[ValleyIs]])

	###################################################################################################
	# STEP 4. Definitions of Theta cycles #############################################################

	# in order to 'detect' a theta cycle I go valley by valley and check if the preceding AND the subsequent 
	# detected peaks are within a distance compatible with the theta cycle length (following the parameters 
	# defined in the first step), c.f. the loop below.

	# declaring variables as empty int arrays
	ThetaCycleBegin = np.array([],dtype=int)
	ThetaCycleEnd = np.array([],dtype=int)
	CycleRefs = np.array([],dtype=int)

	# loop over valleys
	for Valleyi in ValleyIs:
	    
		# gets first peak BEFORE valley
		aux = PeakIs[(PeakIs>(Valleyi-MaxPeak2ValleyDistance))&(PeakIs<Valleyi)]
		if np.size(aux)>0:
			Peak1 = aux[np.argmax(aux)]
		else:
			Peak1 = -np.inf
	    
		# gets first peak AFTER valley
		aux = PeakIs[(PeakIs<(Valleyi+MaxPeak2ValleyDistance))&(PeakIs>Valleyi)]
		if np.size(aux)>0:
	    		Peak2 = aux[np.argmin(aux)]
		else:
			Peak2 = -np.inf
	    
		# checks if both peak-valley distances are larger than minimum allowed
		PeakValleyCheck1 = min((Valleyi-Peak1),(Peak2-Valleyi))\
		                    >=MinPeak2ValleyDistance
		# checks if both peak-valley distances are smaller than maximum allowed
		PeakValleyCheck2 = max((Valleyi-Peak1),(Peak2-Valleyi))\
		                    <=MaxPeak2ValleyDistance
    	    
		# if both conditions are satisfied, get theta cycle
		if PeakValleyCheck1&PeakValleyCheck2:
			if (Peak2-Peak1)<=MaxPeak2PeakDistance:
				ThetaCycleBegin = np.append(ThetaCycleBegin,Peak1)
				ThetaCycleEnd = np.append(ThetaCycleEnd,Peak2)
				CycleRefs = np.append(CycleRefs,Valleyi)

	CyclePeaks = np.asarray([ThetaCycleBegin,ThetaCycleEnd]).T

	# gets rid of cycles with coincident first edges.
	aux = list(CyclePeaks[:,0])
	cycles2remove = list(set([i for (i,x) in enumerate(aux) if aux.count(x) > 1]))
	del aux

	CyclePeaks = np.delete(CyclePeaks,cycles2remove,0)
	CycleTrough = np.delete(CycleRefs,cycles2remove,0)

	nCycles = len(CycleTrough)
	zeroscross1 = np.zeros(nCycles,dtype=int)
	zeroscross2 = np.zeros(nCycles,dtype=int)
	zeroscross3 = np.zeros(nCycles,dtype=int)
	validCycles = np.zeros(nCycles,dtype=bool)
	for cyclei in range(nCycles):

		aux1 = np.arange(CyclePeaks[cyclei,0]-MaxPeak2ValleyDistance,CyclePeaks[cyclei,0],dtype=int)
		aux2 = np.arange(CyclePeaks[cyclei,0],CycleTrough[cyclei],dtype=int)
		aux3 = np.arange(CycleTrough[cyclei],CyclePeaks[cyclei,1],dtype=int)

		cond0 = (np.sum(Theta[aux1]<0)*np.sum(Theta[aux2]<0)*np.sum(Theta[aux3]>0))>0
		if cond0:
			zeroscross1[cyclei] = np.max(np.where(Theta[aux1]<0))+1+(CyclePeaks[cyclei,0]-MaxPeak2ValleyDistance)
			zeroscross2[cyclei] = np.min(np.where(Theta[aux2]<0))+(CyclePeaks[cyclei,0])-1
			zeroscross3[cyclei] = np.min(np.where(Theta[aux3]>0))+(CycleTrough[cyclei])-1

			cond1 = np.sum(Theta[np.arange(zeroscross3[cyclei]+1,CyclePeaks[cyclei,1])]<0)<1
			cond2 = np.sum(Theta[np.arange(zeroscross1[cyclei]+1,CyclePeaks[cyclei,0])]<0)<1
			cond3 = np.sum(Theta[np.arange(zeroscross2[cyclei]+1,CycleTrough[cyclei])]>0)<1
			validCycles[cyclei] = cond1&cond2&cond3

	cycleRefs = np.array([zeroscross1,CyclePeaks[:,0],zeroscross2,CycleTrough,zeroscross3,CyclePeaks[:,1]]).T
	cycleRefs = cycleRefs[validCycles,:]

	return cycleRefs

def getThetaPhases(cycleRefs,signalLen):

	phase = np.zeros(signalLen)+np.nan
	nCycles = np.size(cycleRefs,0)
	for cyclei in range(nCycles):
		phaserefs = cycleRefs[cyclei,:]
		for phaserefi in range(len(phaserefs)-2):
		        initialphase = (-np.pi/2)+(np.pi/2)*phaserefi
		        endphase = (-np.pi/2)+(np.pi/2)*(phaserefi+1)
		        quadrantSamples = range(phaserefs[phaserefi],phaserefs[phaserefi+1])
		        quadrantTimeLength =  len(quadrantSamples)
		        phase[quadrantSamples] = np.linspace(initialphase,endphase,quadrantTimeLength+1)[0:-1]
		
	validPhases = np.where(~np.isnan(phase))[0]
	phase[validPhases[phase[validPhases]<0]] += 2*np.pi

	return phase

#########################################################################################################
#########################################################################################################

#########################################################################################################
#### PEAK DETECTION #####################################################################################
################ __author__ = "Marcos Duarte, https://github.com/demotu/BMC"        #####################
################     ____version__ = "1.0.4"                                        #####################
################     ____license__ = "MIT"                                          #####################
#########################################################################################################

def detectPeaks(x, mph=None, mpd=1, threshold=0, edge='rising',
                 kpsh=False, valley=False, show=False, ax=None):

    """Detect peaks in data based on their amplitude and other features.

    Parameters
    ----------
    x : 1D array_like
        data.
    mph : {None, number}, optional (default = None)
        detect peaks that are greater than minimum peak height.
    mpd : positive integer, optional (default = 1)
        detect peaks that are at least separated by minimum peak distance (in
        number of data).
    threshold : positive number, optional (default = 0)
        detect peaks (valleys) that are greater (smaller) than `threshold`
        in relation to their immediate neighbors.
    edge : {None, 'rising', 'falling', 'both'}, optional (default = 'rising')
        for a flat peak, keep only the rising edge ('rising'), only the
        falling edge ('falling'), both edges ('both'), or don't detect a
        flat peak (None).
    kpsh : bool, optional (default = False)
        keep peaks with same height even if they are closer than `mpd`.
    valley : bool, optional (default = False)
        if True (1), detect valleys (local minima) instead of peaks.
    show : bool, optional (default = False)
        if True (1), plot data in matplotlib figure.
    ax : a matplotlib.axes.Axes instance, optional (default = None).

    Returns
    -------
    ind : 1D array_like
        indeces of the peaks in `x`.

    Notes
    -----
    The detection of valleys instead of peaks is performed internally by simply
    negating the data: `ind_valleys = detect_peaks(-x)`
    
    The function can handle NaN's 

    See this IPython Notebook [1]_.

    References
    ----------
    .. [1] http://nbviewer.ipython.org/github/demotu/BMC/blob/master/notebooks/DetectPeaks.ipynb

    Examples
    --------
    >>> from detect_peaks import detect_peaks
    >>> x = np.random.randn(100)
    >>> x[60:81] = np.nan
    >>> # detect all peaks and plot data
    >>> ind = detect_peaks(x, show=True)
    >>> print(ind)

    >>> x = np.sin(2*np.pi*5*np.linspace(0, 1, 200)) + np.random.randn(200)/5
    >>> # set minimum peak height = 0 and minimum peak distance = 20
    >>> detect_peaks(x, mph=0, mpd=20, show=True)

    >>> x = [0, 1, 0, 2, 0, 3, 0, 2, 0, 1, 0]
    >>> # set minimum peak distance = 2
    >>> detect_peaks(x, mpd=2, show=True)

    >>> x = np.sin(2*np.pi*5*np.linspace(0, 1, 200)) + np.random.randn(200)/5
    >>> # detection of valleys instead of peaks
    >>> detect_peaks(x, mph=0, mpd=20, valley=True, show=True)

    >>> x = [0, 1, 1, 0, 1, 1, 0]
    >>> # detect both edges
    >>> detect_peaks(x, edge='both', show=True)

    >>> x = [-2, 1, -2, 2, 1, 1, 3, 0]
    >>> # set threshold = 2
    >>> detect_peaks(x, threshold = 2, show=True)
    """

    x = np.atleast_1d(x).astype('float64')
    if x.size < 3:
        return np.array([], dtype=int)
    if valley:
        x = -x
    # find indices of all peaks
    dx = x[1:] - x[:-1]
    # handle NaN's
    indnan = np.where(np.isnan(x))[0]
    if indnan.size:
        x[indnan] = np.inf
        dx[np.where(np.isnan(dx))[0]] = np.inf
    ine, ire, ife = np.array([[], [], []], dtype=int)
    if not edge:
        ine = np.where((np.hstack((dx, 0)) < 0) & (np.hstack((0, dx)) > 0))[0]
    else:
        if edge.lower() in ['rising', 'both']:
            ire = np.where((np.hstack((dx, 0)) <= 0) & (np.hstack((0, dx)) > 0))[0]
        if edge.lower() in ['falling', 'both']:
            ife = np.where((np.hstack((dx, 0)) < 0) & (np.hstack((0, dx)) >= 0))[0]
    ind = np.unique(np.hstack((ine, ire, ife)))
    # handle NaN's
    if ind.size and indnan.size:
        # NaN's and values close to NaN's cannot be peaks
        ind = ind[np.in1d(ind, np.unique(np.hstack((indnan, indnan-1, indnan+1))), invert=True)]
    # first and last values of x cannot be peaks
    if ind.size and ind[0] == 0:
        ind = ind[1:]
    if ind.size and ind[-1] == x.size-1:
        ind = ind[:-1]
    # remove peaks < minimum peak height
    if ind.size and mph is not None:
        ind = ind[x[ind] >= mph]
    # remove peaks - neighbors < threshold
    if ind.size and threshold > 0:
        dx = np.min(np.vstack([x[ind]-x[ind-1], x[ind]-x[ind+1]]), axis=0)
        ind = np.delete(ind, np.where(dx < threshold)[0])
    # detect small peaks closer than minimum peak distance
    if ind.size and mpd > 1:
        ind = ind[np.argsort(x[ind])][::-1]  # sort ind by peak height
        idel = np.zeros(ind.size, dtype=bool)
        for i in range(ind.size):
            if not idel[i]:
                # keep peaks with the same height if kpsh is True
                idel = idel | (ind >= ind[i] - mpd) & (ind <= ind[i] + mpd) \
                    & (x[ind[i]] > x[ind] if kpsh else True)
                idel[i] = 0  # Keep current peak
        # remove the small peaks and sort back the indices by their occurrence
        ind = np.sort(ind[~idel])

    if show:
        if indnan.size:
            x[indnan] = np.nan
        if valley:
            x = -x
        _plot(x, mph, mpd, threshold, edge, valley, ax, ind)

    return ind

#########################################################################################################
#########################################################################################################

#########################################################################################################
#### WAVELET SPECTROGRAM ################################################################################
#########################################################################################################

def WvSpectrogram(raw,SamplingRate,frequencies,runSpectrogram=True,runPhases=False,s=1,w=5):

        if np.size(frequencies)>1:
                tfr = np.zeros((len(frequencies),len(raw)),dtype=complex) 
		for freq_i in range(len(frequencies)):

                        freq = frequencies[freq_i]
			
			# call function below 
                        tfr[freq_i,:] = WVfiltering(raw,SamplingRate,freq) 

	else:
		tfr = WVfiltering(raw,SamplingRate,frequencies)

	if runSpectrogram:
		spectrogram = np.abs(tfr)
	else:
		spectrogram = None

	if runPhases:
		phases = np.angle(tfr)
	else:
		phases = None
		
	return spectrogram,tfr,phases

def WVfiltering(Signal,SamplingRate,DesiredFreq):

	# computing the length of the wavelet for the desired frequency
	WaveletLength = 10.*SamplingRate/DesiredFreq			

	# constructs morlet wavelet with given parameters
	MorletWav = sig.morlet(WaveletLength,w=5,s=1,complete=True)

	# cutting borders
	CumulativeEnvelope = np.cumsum(np.abs(MorletWav))/np.sum(np.abs(MorletWav))
	Cut1 = next(i for (i,val) in enumerate(CumulativeEnvelope[::-1]) if val<=(1./10000)) 
	Cut2 = Cut1
	Cut1 = len(CumulativeEnvelope)-Cut1-1
	MorletWav = MorletWav[range(Cut1,Cut2)]

	# normalizes wavelet energy
	MorletWav = MorletWav/(.5*sum(abs(MorletWav)))

	# convolving signal with wavelet
	WVFilteredSignal = np.convolve(Signal,MorletWav,'same')

	return WVFilteredSignal

def computeWVspect4ICA(baseSession,ChLabel,freqs=freqs,fs=lfpSR):

	ChLabel = str(ChLabel)

        filename = baseSession+'.emd.'+ChLabel
        imfs = np.load(filename)

	mainfreqs = getIMFmainfreq(baseSession,ChLabel)
	validIMFs = np.where(~(np.isnan(mainfreqs)))[0]
	IMFs2ICA = validIMFs[mainfreqs[validIMFs]>15]
	FiltSignal4ICA = np.sum(imfs[IMFs2ICA,:],axis=0)
	WVspect4ICA,_,_ = WvSpectrogram(FiltSignal4ICA,SamplingRate=lfpSR,frequencies=freqs)

	return WVspect4ICA

#########################################################################################################
#### GENERAL FUNCTIONS ##################################################################################
#########################################################################################################

def next_power_of_2(n):

	'''Return next power of 2 greater than or equal to n'''
	n -= 1                 # short for "n = n - 1"
	shift = 1
	while (n+1) & n:       # the operator "&" is a bitwise operator: it compares every bit of (n+1) and n, and returns those bits that are present in both
		n |= n >> shift    
		shift <<= 1        # the operator "<<" means "left bitwise shift": this comes down to "shift = shift**2"
	return n + 1

def runHilbert(signal):

	hilbert = sig.hilbert(signal,next_power_of_2(len(signal)))[np.arange(len(signal))]

	return hilbert

def printTime(prefix):
	print prefix+time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
	sys.stdout.flush()

def bold(string):
        
        b0 = "\033[1m"
        b1 = "\033[0;0m"
        
        return b0+string+b1

#########################################################################################################
#### PLOTTING FUNCTIONS #################################################################################
#########################################################################################################

def getSamplesWithinEdges(edges):

	if len(np.shape(edges))<2:
       		edges = edges.reshape(1,2)
	samples = np.array([],dtype=int)
	NofCycles = len(edges)    
	for cyclei in range(NofCycles):
		cyclesamplesAux = np.arange(edges[cyclei,0],edges[cyclei,1],dtype=int)
		samples = np.hstack((samples,cyclesamplesAux))
	samples = np.unique(samples)

	return samples

def getAmpPhaseMatrix(phase,amplitude,nbins):

	if len(np.shape(amplitude))<2:
		amplitude = amplitude.reshape(1,-1)

	if not (len(phase)==np.shape(amplitude)[-1]):
		print(bold('ERROR: ')+' phase and amplitude signals do not have same size.')
		return None,None

	if np.abs(np.nanmedian(phase)-np.pi)<np.pi/4:
		BinEdges = np.linspace(0,2*np.pi,nbins+1)
	elif np.abs(np.nanmedian(phase))<np.pi/4:
		BinEdges = np.linspace(-np.pi,np.pi,nbins+1)

	PhaseBinCentres = np.convolve(BinEdges,[.5,.5])
	PhaseBinCentres = np.delete(PhaseBinCentres,[0,len(PhaseBinCentres)-1])

	phase = np.copy(phase)
	phase[np.isnan(phase)] = -np.inf

	PhaseSamples = [None]*nbins
	for bin_i in range(nbins):
		aux = np.where((BinEdges[bin_i]<=phase)&(phase<BinEdges[bin_i+1]))
    		PhaseSamples[bin_i] = aux[0]
	
	MeanAmpMat = np.zeros((len(amplitude),nbins))
	for freq_i in range(len(amplitude)):

		AmplitudeSignal = amplitude[freq_i,:]

		MeanAmp = np.zeros(nbins)
		for bin_i in range(nbins):
			MeanAmp[bin_i] = np.mean(AmplitudeSignal[PhaseSamples[bin_i]])
		MeanAmpMat[freq_i,:] = MeanAmp

	return MeanAmpMat,PhaseBinCentres

def meantSCcycle(base,ChLabel,sessions,pltfreqs = np.arange(15,110,5),nphasebins = 16):

	tSCdata = [None]*len(sessions)
	thetaCycles = [None]*len(sessions)
	thetaPhase = [None]*len(sessions)
	for (si,s) in enumerate(sessions):

		baseSession = base+'_'+str(s)

		filename = baseSession+'.tSCs.'+'ica.'+str(ChLabel)
		tSCdata[si] = np.load(filename).item()

		thetaCycles[si] = np.load(baseSession+'.theta.cycles.'+str(ChLabel))
		thetaPhase[si] = np.load(baseSession+'.theta.phase.'+str(ChLabel))

	ntSCs = np.size(tSCdata[0]['tSCs'],1)
	projections = np.array([]).reshape(0,ntSCs)
	for (si,s) in enumerate(sessions):
		projections = np.concatenate((projections,tSCdata[si]['projections']))
	thrs = np.percentile(projections,90,axis=0)

	tSCprofile = np.zeros((1+ntSCs,len(pltfreqs),nphasebins))
	nCycles = np.zeros(1+ntSCs)
	for (si,s) in enumerate(sessions):
	    
		baseSession = base+'_'+str(s)
		
		lfp = np.load(baseSession+'.eeg.'+str(ChLabel))
		spectrogram,_,_ = WvSpectrogram(lfp,SamplingRate=lfpSR,frequencies=pltfreqs)
		
		edges = thetaCycles[si][:,np.array([0,4])]
		samples = getSamplesWithinEdges(edges)
		ampphase,phasebins = getAmpPhaseMatrix(thetaPhase[si][samples],\
		                                            spectrogram[:,samples],\
		                                            nbins=nphasebins)
		tSCprofile[0] += ampphase*np.size(edges,0)
		nCycles[0] += np.size(edges,0)
		
		for tSCi in range(ntSCs):
		
		        cycleIDs = tSCdata[si]['projections'][:,tSCi]>[thrs[tSCi]]
		    
		        if np.sum(cycleIDs)>0:
		                edges = thetaCycles[si][cycleIDs,:][:,np.array([0,4])]
		                samples = getSamplesWithinEdges(edges)
		                ampphase,phasebins = getAmpPhaseMatrix(thetaPhase[si][samples],\
		                                                           spectrogram[:,samples],nbins=nphasebins)
		                tSCprofile[1+tSCi] += ampphase*np.sum(cycleIDs)
		                nCycles[1+tSCi] += np.sum(cycleIDs)
		                
	for (i,tSCprofile0) in enumerate(tSCprofile):
		tSCprofile[i] = tSCprofile0/nCycles[i]

	return tSCprofile,pltfreqs,phasebins,tSCdata[0]['mainfreqs']

def plotMeantSCcycle(base,ChLabel,sessions,pltfreqs = np.arange(15,110,5),nphasebins = 16, cmap='magma_r',nlevels=30):

	import matplotlib.pyplot as plt
	plt.rcParams['svg.fonttype'] = 'none'

	tSCprofile,pltfreqs,phasebins,mainfreqs = meantSCcycle(base,ChLabel,sessions,pltfreqs = np.arange(15,110,5),nphasebins = 16)

	plt.figure(figsize=(15,8))
	levels = np.linspace(np.percentile(tSCprofile,1),np.percentile(tSCprofile,99.75),nlevels)
	for (i,tSCi) in enumerate(np.argsort(np.concatenate((np.array([0]),mainfreqs)))):
		plt.subplot(2,3,i+1)

		ampphase0 = tSCprofile[tSCi] 
		ampphase0 = np.concatenate((ampphase0,ampphase0),axis=1)
		phasebins0 = np.concatenate((phasebins,phasebins+2*np.pi)) 
		ampphase0[ampphase0<np.min(levels)] = np.min(levels)
		ampphase0[ampphase0>np.max(levels)] = np.max(levels)

		plt.contourf(phasebins0,pltfreqs,ampphase0,levels,cmap=cmap) #'jet'
		cosPhs = np.linspace(np.min(phasebins0),np.max(phasebins0),50)
		cos = np.cos(cosPhs)*(np.max(pltfreqs)-np.min(pltfreqs))/6.+np.mean(pltfreqs)
		plt.plot(cosPhs,cos,'w')
		plt.xticks(np.arange(np.pi/2,4*np.pi,np.pi/2),np.arange(np.pi/2,4*np.pi,np.pi/2)*180/np.pi)
		plt.colorbar()
		plt.grid(True,color='w',alpha=.3)
		
		if i == 0:
		        plt.title('All cycles')
		else:
		        plt.title('tSC #'+str(i))

		plt.xlabel('theta phase',fontsize=14)
		plt.ylabel('frequency (Hz)',fontsize=14)
		
	plt.tight_layout()

#########################################################################################################
#########################################################################################################

if __name__ == "__main__":

	import sys as sys

	sessions = None
	ChLabels = None
	nCPUs = 0
	lfpSR = 1250.

	nArgs = len(sys.argv)
	base = sys.argv[1]
	for argi in range(2,nArgs):

		if '=' in sys.argv[argi]:
			strindex = sys.argv[argi].index('=')+1
			aux = sys.argv[argi][strindex:]

		if 'ses=' in sys.argv[argi]:
			sessions = np.unique([int(x) for x in aux.split(',')])

		if 'ch=' in sys.argv[argi]:
			ChLabels = np.unique([int(x) for x in aux.split(',')])
		else:
			import glob as glob
			filenames = glob.glob(base+'*.eeg*')			

		if 'freqs=' in sys.argv[argi]:
			freqs = np.unique([int(x) for x in aux.split(',')])
		if 'nPCs=' in sys.argv[argi]:
			nPCs = int(aux)
		if 'dimrec=' in sys.argv[argi]:
			dimrec = aux

		if 'sr=' in sys.argv[argi]:
			lfpSR = float(aux)

		if 'nCPUs=' in sys.argv[argi]:
			nCPUs = int(aux)

		if '--matchSessions' in sys.argv[argi]:
			matchSessions = True

	if sessions is None:
		import glob as glob
		filenames = glob.glob(base+'_*.eeg*')
		sessions = np.array([])
		for filename in filenames:
			indx1 = filename.index('.eeg')
			aux = np.array([filename[len(base)+1:indx1]])
			sessions = np.concatenate((sessions,aux))
	sessions = np.unique(sessions)

	if ChLabels is None:
		import glob as glob
		filenames = glob.glob(base+'_'+str(sessions[0])+'.eeg*')
		ChLabels = np.array([])
		for filename in filenames:
			indx1 = filename.index('.eeg')
			aux = np.array([filename[indx1+5:]])
			ChLabels = np.concatenate((ChLabels,aux))
	ChLabels = np.unique(ChLabels)
	
	run(base,ChLabels,sessions,freqs=freqs,nPCs=nPCs,matchSessions=matchSessions,dimrec=dimrec,nWorkers=nCPUs)
