load('SuMAP.mat')

figure
image(Su.I);hold on
for i=1:128
plot(Su.X,Su.Y,'ro');hold on
end
axis equal
